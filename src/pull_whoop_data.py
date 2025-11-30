"""
Whoop API Data Extractor
Extracts recovery, sleep, and workout data from Whoop API and stores in PostgreSQL.
"""

import datetime
import logging
import os
from typing import Any

import requests
from dotenv import load_dotenv
from sqlalchemy import select

from database import get_db_session_context
from models import UserCredentials, WhoopRecovery, WhoopSleep, WhoopWorkout
from security import decrypt_data_for_user, encrypt_data_for_user
from sync_manager import SyncResult, upsert_data
from whoop_schemas import WhoopRecoveryParser, WhoopSleepParser, WhoopWorkoutParser

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WhoopAPIClient:
    """Whoop API client with OAuth2 token management."""

    def __init__(self, access_token: str, refresh_token: str, user_id: int):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.user_id = user_id
        self.base_url = "https://api.prod.whoop.com/developer/v1"
        self.client_id = os.getenv("WHOOP_CLIENT_ID")
        self.client_secret = os.getenv("WHOOP_CLIENT_SECRET")

    def _get_headers(self) -> dict:
        """Get request headers with auth token."""
        return {"Authorization": f"Bearer {self.access_token}"}

    def _refresh_access_token(self) -> bool:
        """Refresh access token using refresh token."""
        try:
            response = requests.post(
                "https://api.prod.whoop.com/oauth/oauth2/token",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self.refresh_token,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
                timeout=30,
            )

            if response.status_code == 200:
                tokens = response.json()
                self.access_token = tokens["access_token"]
                self.refresh_token = tokens.get("refresh_token", self.refresh_token)

                with get_db_session_context() as db:
                    creds = db.scalars(
                        select(UserCredentials).where(
                            UserCredentials.user_id == self.user_id
                        )
                    ).first()

                    if creds:
                        creds.encrypted_whoop_access_token = encrypt_data_for_user(
                            self.access_token, self.user_id
                        )
                        creds.encrypted_whoop_refresh_token = encrypt_data_for_user(
                            self.refresh_token, self.user_id
                        )
                        creds.whoop_token_expires_at = (
                            datetime.datetime.utcnow()
                            + datetime.timedelta(seconds=tokens.get("expires_in", 3600))
                        )
                        db.commit()

                logger.info(f"Refreshed Whoop access token for user {self.user_id}")
                return True

            logger.error(
                f"Failed to refresh Whoop token: {response.status_code} {response.text}"
            )
            return False

        except Exception as e:
            logger.error(f"Error refreshing Whoop token: {e}")
            return False

    def _make_request(self, endpoint: str, params: dict | None = None) -> dict | None:
        """Make API request with automatic token refresh."""
        try:
            response = requests.get(
                f"{self.base_url}/{endpoint}",
                headers=self._get_headers(),
                params=params or {},
                timeout=30,
            )

            if response.status_code == 401:
                logger.info("Whoop token expired, refreshing...")
                if self._refresh_access_token():
                    response = requests.get(
                        f"{self.base_url}/{endpoint}",
                        headers=self._get_headers(),
                        params=params or {},
                        timeout=30,
                    )

            if response.status_code == 200:
                result: dict = response.json()
                return result

            logger.error(
                f"Whoop API request failed: {response.status_code} {response.text}"
            )
            return None

        except Exception as e:
            logger.error(f"Error making Whoop API request: {e}")
            return None

    def get_recovery_data(
        self, start_date: datetime.date, end_date: datetime.date
    ) -> list[dict]:
        results: list[dict] = []

        start_str = start_date.isoformat()
        end_str = end_date.isoformat()

        response = self._make_request(
            "cycle",
            params={
                "start": f"{start_str}T00:00:00.000Z",
                "end": f"{end_str}T23:59:59.999Z",
            },
        )

        if not response:
            return results

        cycles = response.get("records", [])

        for cycle in cycles:
            cycle_id = cycle.get("id")
            if not cycle_id:
                continue

            recovery_response = self._make_request(f"cycle/{cycle_id}/recovery")

            if recovery_response:
                start_time = cycle.get("start")
                if start_time:
                    date_obj = datetime.datetime.fromisoformat(
                        start_time.replace("Z", "+00:00")
                    ).date()
                    recovery_response["date"] = date_obj
                    results.append(recovery_response)

        return results

    def get_sleep_data(
        self, start_date: datetime.date, end_date: datetime.date
    ) -> list[dict]:
        results: list[dict] = []

        start_str = start_date.isoformat()
        end_str = end_date.isoformat()

        response = self._make_request(
            "activity/sleep",
            params={
                "start": f"{start_str}T00:00:00.000Z",
                "end": f"{end_str}T23:59:59.999Z",
            },
        )

        if not response:
            return results

        sleeps = response.get("records", [])

        for sleep in sleeps:
            start_time = sleep.get("start")
            if start_time:
                date_obj = datetime.datetime.fromisoformat(
                    start_time.replace("Z", "+00:00")
                ).date()
                sleep["date"] = date_obj
                results.append(sleep)

        return results

    def get_workout_data(
        self, start_date: datetime.date, end_date: datetime.date
    ) -> list[dict]:
        results: list[dict] = []

        start_str = start_date.isoformat()
        end_str = end_date.isoformat()

        response = self._make_request(
            "activity/workout",
            params={
                "start": f"{start_str}T00:00:00.000Z",
                "end": f"{end_str}T23:59:59.999Z",
            },
        )

        if not response:
            return results

        workouts = response.get("records", [])

        for workout in workouts:
            start_time = workout.get("start")
            if start_time:
                date_obj = datetime.datetime.fromisoformat(
                    start_time.replace("Z", "+00:00")
                ).date()
                workout["date"] = date_obj
                results.append(workout)

        return results


def sync_whoop_recovery(
    client: WhoopAPIClient,
    user_id: int,
    start_date: datetime.date,
    end_date: datetime.date,
) -> SyncResult:
    """Sync Whoop recovery data."""
    sync_result = SyncResult(source="whoop", data_type="recovery")

    try:
        recovery_data = client.get_recovery_data(start_date, end_date)

        with get_db_session_context() as db:
            for item in recovery_data:
                try:
                    parsed = WhoopRecoveryParser.from_whoop_response(
                        item, item.get("date")
                    )
                    if not parsed:
                        sync_result.records_skipped += 1
                        continue

                    data_dict = {
                        "user_id": user_id,
                        "date": item.get("date"),
                        **parsed.model_dump(),
                    }

                    upsert_data(
                        db,
                        WhoopRecovery,
                        data_dict,
                        ["date"],
                        user_id,
                        sync_result,
                    )

                except Exception as e:
                    sync_result.add_error(f"Error processing recovery: {str(e)}")
                    sync_result.records_skipped += 1

            db.commit()

    except Exception as e:
        sync_result.add_error(f"Sync error: {str(e)}")

    return sync_result


def sync_whoop_sleep(
    client: WhoopAPIClient,
    user_id: int,
    start_date: datetime.date,
    end_date: datetime.date,
) -> SyncResult:
    """Sync Whoop sleep data."""
    sync_result = SyncResult(source="whoop", data_type="sleep")

    try:
        sleep_data = client.get_sleep_data(start_date, end_date)

        with get_db_session_context() as db:
            for item in sleep_data:
                try:
                    parsed = WhoopSleepParser.from_whoop_response(
                        item, item.get("date")
                    )
                    if not parsed:
                        sync_result.records_skipped += 1
                        continue

                    data_dict = {
                        "user_id": user_id,
                        "date": item.get("date"),
                        **parsed.model_dump(),
                    }

                    upsert_data(
                        db,
                        WhoopSleep,
                        data_dict,
                        ["date"],
                        user_id,
                        sync_result,
                    )

                except Exception as e:
                    sync_result.add_error(f"Error processing sleep: {str(e)}")
                    sync_result.records_skipped += 1

            db.commit()

    except Exception as e:
        sync_result.add_error(f"Sync error: {str(e)}")

    return sync_result


def sync_whoop_workouts(
    client: WhoopAPIClient,
    user_id: int,
    start_date: datetime.date,
    end_date: datetime.date,
) -> SyncResult:
    """Sync Whoop workout data."""
    sync_result = SyncResult(source="whoop", data_type="workouts")

    try:
        workout_data = client.get_workout_data(start_date, end_date)

        with get_db_session_context() as db:
            for item in workout_data:
                try:
                    parsed = WhoopWorkoutParser.from_whoop_response(item)
                    if not parsed:
                        sync_result.records_skipped += 1
                        continue

                    data_dict = {
                        "user_id": user_id,
                        "date": item.get("date"),
                        **parsed.model_dump(),
                    }

                    upsert_data(
                        db,
                        WhoopWorkout,
                        data_dict,
                        ["date", "start_time"],
                        user_id,
                        sync_result,
                    )

                except Exception as e:
                    sync_result.add_error(f"Error processing workout: {str(e)}")
                    sync_result.records_skipped += 1

            db.commit()

    except Exception as e:
        sync_result.add_error(f"Sync error: {str(e)}")

    return sync_result


def sync_whoop_data_for_user(user_id: int, days: int = 90) -> dict[str, Any]:
    """
    Main function to sync all Whoop data for a user.

    Args:
        user_id: User ID to sync data for
        days: Number of days back to sync (default 90)

    Returns:
        dict: Summary of sync results
    """
    try:
        with get_db_session_context() as db:
            creds = db.scalars(
                select(UserCredentials).where(UserCredentials.user_id == user_id)
            ).first()

            if not creds or not creds.encrypted_whoop_access_token:
                return {"error": "No Whoop credentials found for user"}

            access_token = decrypt_data_for_user(
                creds.encrypted_whoop_access_token, user_id
            )
            refresh_token = decrypt_data_for_user(
                creds.encrypted_whoop_refresh_token, user_id
            )

    except Exception as e:
        return {"error": f"Failed to get user credentials: {str(e)}"}

    try:
        client = WhoopAPIClient(access_token, refresh_token, user_id)

        end_date = datetime.date.today()
        start_date = end_date - datetime.timedelta(days=days)

        logger.info(
            f"Starting Whoop sync for user {user_id} from {start_date} to {end_date}"
        )

        recovery_result = sync_whoop_recovery(client, user_id, start_date, end_date)
        sleep_result = sync_whoop_sleep(client, user_id, start_date, end_date)
        workout_result = sync_whoop_workouts(client, user_id, start_date, end_date)

        results = [recovery_result, sleep_result, workout_result]

        summary = {
            "user_id": user_id,
            "sync_date": datetime.datetime.utcnow().isoformat(),
            "date_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
            "results": [r.get_summary() for r in results],
            "total_records_processed": sum(r.records_processed for r in results),
            "total_records_created": sum(r.records_created for r in results),
            "total_records_updated": sum(r.records_updated for r in results),
            "total_errors": sum(len(r.errors) for r in results),
            "success": all(r.success for r in results),
        }

        logger.info(f"Whoop sync completed for user {user_id}: {summary}")
        return summary

    except Exception as e:
        error_msg = f"Failed to sync Whoop data for user {user_id}: {str(e)}"
        logger.error(error_msg)
        return {"error": error_msg, "user_id": user_id}


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        user_id = int(sys.argv[1])
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 90

        result = sync_whoop_data_for_user(user_id, days)
        print(f"Sync result: {result}")
    else:
        print("Usage: python pull_whoop_data.py <user_id> [days]")
