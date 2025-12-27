import datetime
import os
import time
from typing import Any

import requests
from dotenv import load_dotenv
from sqlalchemy import select

from database import get_db_session_context
from enums import DataSource, DataType
from logging_config import get_logger
from models import UserCredentials, WhoopCycle, WhoopRecovery, WhoopSleep, WhoopWorkout
from security import decrypt_data_for_user, encrypt_data_for_user
from sync_manager import SyncResult, upsert_data
from whoop_schemas import (
    WhoopCycleParser,
    WhoopRecoveryParser,
    WhoopSleepParser,
    WhoopWorkoutParser,
)

load_dotenv()

logger = get_logger(__name__)


class WhoopAPIClient:
    """Whoop API client with OAuth2 token management."""

    def __init__(self, access_token: str, refresh_token: str, user_id: int):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.user_id = user_id
        self.base_url = "https://api.prod.whoop.com/developer/v2"
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
        """Make API request with automatic token refresh and rate limiting."""
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

            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 60))
                logger.warning(f"Rate limited, waiting {retry_after}s...")
                time.sleep(retry_after)
                return self._make_request(endpoint, params)

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

    def _paginated_request(
        self, endpoint: str, params: dict | None = None, limit: int = 25
    ) -> list[dict]:
        """Make paginated API request, fetching all pages."""
        all_records: list[dict] = []
        request_params = dict(params or {})
        request_params["limit"] = limit
        page_count = 0
        max_pages = 1000  # Safety limit

        while page_count < max_pages:
            response = self._make_request(endpoint, request_params)
            if not response:
                break

            records = response.get("records", [])
            all_records.extend(records)
            page_count += 1

            next_token = response.get("next_token")
            if not next_token:
                break

            request_params["nextToken"] = next_token

            # Rate limiting: ~0.6s between requests = 100 req/min
            time.sleep(0.6)

            if page_count % 10 == 0:
                logger.info(
                    f"Fetched {len(all_records)} records from {page_count} pages"
                )

        logger.info(f"Total: {len(all_records)} records from {page_count} pages")
        return all_records

    def get_recovery_data(
        self,
        start_date: datetime.date | None = None,
        end_date: datetime.date | None = None,
    ) -> list[dict]:
        results: list[dict] = []

        params: dict[str, str] = {}
        if start_date:
            params["start"] = f"{start_date.isoformat()}T00:00:00.000Z"
        if end_date:
            params["end"] = f"{end_date.isoformat()}T23:59:59.999Z"

        recoveries = self._paginated_request("recovery", params)

        for recovery in recoveries:
            created_at = recovery.get("created_at")
            if created_at:
                date_obj = datetime.datetime.fromisoformat(
                    created_at.replace("Z", "+00:00")
                ).date()
                recovery["date"] = date_obj
                results.append(recovery)

        return results

    def get_sleep_data(
        self,
        start_date: datetime.date | None = None,
        end_date: datetime.date | None = None,
    ) -> list[dict]:
        params: dict[str, str] = {}
        if start_date:
            params["start"] = f"{start_date.isoformat()}T00:00:00.000Z"
        if end_date:
            params["end"] = f"{end_date.isoformat()}T23:59:59.999Z"

        sleeps = self._paginated_request("activity/sleep", params)
        sleep_by_date: dict[datetime.date, dict] = {}

        for sleep in sleeps:
            if sleep.get("nap", False):
                continue

            start_time = sleep.get("start")
            if not start_time:
                continue

            date_obj = datetime.datetime.fromisoformat(
                start_time.replace("Z", "+00:00")
            ).date()
            sleep["date"] = date_obj

            score = sleep.get("score", {})
            stage_summary = score.get("stage_summary", {})
            duration = stage_summary.get("total_in_bed_time_milli", 0) or 0

            if date_obj not in sleep_by_date:
                sleep_by_date[date_obj] = sleep
            else:
                existing_score = sleep_by_date[date_obj].get("score", {})
                existing_summary = existing_score.get("stage_summary", {})
                existing_duration = (
                    existing_summary.get("total_in_bed_time_milli", 0) or 0
                )
                if duration > existing_duration:
                    sleep_by_date[date_obj] = sleep

        return list(sleep_by_date.values())

    def get_workout_data(
        self,
        start_date: datetime.date | None = None,
        end_date: datetime.date | None = None,
    ) -> list[dict]:
        results: list[dict] = []

        params: dict[str, str] = {}
        if start_date:
            params["start"] = f"{start_date.isoformat()}T00:00:00.000Z"
        if end_date:
            params["end"] = f"{end_date.isoformat()}T23:59:59.999Z"

        workouts = self._paginated_request("activity/workout", params)

        for workout in workouts:
            start_time = workout.get("start")
            if start_time:
                date_obj = datetime.datetime.fromisoformat(
                    start_time.replace("Z", "+00:00")
                ).date()
                workout["date"] = date_obj
                results.append(workout)

        return results

    def get_cycle_data(
        self,
        start_date: datetime.date | None = None,
        end_date: datetime.date | None = None,
    ) -> list[dict]:
        """Get physiological cycle (daily summary) data with strain."""
        params: dict[str, str] = {}
        if start_date:
            params["start"] = f"{start_date.isoformat()}T00:00:00.000Z"
        if end_date:
            params["end"] = f"{end_date.isoformat()}T23:59:59.999Z"

        cycles = self._paginated_request("cycle", params)

        cycles_by_date: dict[datetime.date, dict] = {}
        for cycle in cycles:
            start_time = cycle.get("start")
            if start_time:
                date_obj = datetime.datetime.fromisoformat(
                    start_time.replace("Z", "+00:00")
                ).date()
                cycle["date"] = date_obj
                existing = cycles_by_date.get(date_obj)
                if existing is None:
                    cycles_by_date[date_obj] = cycle
                else:
                    existing_strain = existing.get("score", {}).get("strain") or 0
                    new_strain = cycle.get("score", {}).get("strain") or 0
                    if new_strain > existing_strain:
                        cycles_by_date[date_obj] = cycle

        return list(cycles_by_date.values())


def sync_whoop_recovery(
    client: WhoopAPIClient,
    user_id: int,
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
) -> SyncResult:
    sync_result = SyncResult(
        source=DataSource.WHOOP, data_type=DataType.RECOVERY, user_id=user_id
    )

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
            sync_result.success = True

    except Exception as e:
        sync_result.add_error(f"Sync error: {str(e)}")

    return sync_result


def sync_whoop_sleep(
    client: WhoopAPIClient,
    user_id: int,
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
) -> SyncResult:
    sync_result = SyncResult(
        source=DataSource.WHOOP, data_type=DataType.SLEEP, user_id=user_id
    )

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
            sync_result.success = True

    except Exception as e:
        sync_result.add_error(f"Sync error: {str(e)}")

    return sync_result


def sync_whoop_workouts(
    client: WhoopAPIClient,
    user_id: int,
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
) -> SyncResult:
    sync_result = SyncResult(
        source=DataSource.WHOOP, data_type=DataType.WORKOUTS, user_id=user_id
    )

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
            sync_result.success = True

    except Exception as e:
        sync_result.add_error(f"Sync error: {str(e)}")

    return sync_result


def sync_whoop_cycles(
    client: WhoopAPIClient,
    user_id: int,
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
) -> SyncResult:
    """Sync Whoop physiological cycles (daily strain summaries)."""
    sync_result = SyncResult(
        source=DataSource.WHOOP, data_type=DataType.CYCLES, user_id=user_id
    )

    try:
        cycle_data = client.get_cycle_data(start_date, end_date)

        with get_db_session_context() as db:
            for item in cycle_data:
                try:
                    parsed = WhoopCycleParser.from_whoop_response(
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
                        WhoopCycle,
                        data_dict,
                        ["date"],
                        user_id,
                        sync_result,
                    )

                except Exception as e:
                    sync_result.add_error(f"Error processing cycle: {str(e)}")
                    sync_result.records_skipped += 1

            db.commit()
            sync_result.success = True

    except Exception as e:
        sync_result.add_error(f"Sync error: {str(e)}")

    return sync_result


def sync_whoop_data_for_user(
    user_id: int, days: int = 90, full_sync: bool = False
) -> dict[str, Any]:
    try:
        with get_db_session_context() as db:
            creds = db.scalars(
                select(UserCredentials).where(UserCredentials.user_id == user_id)
            ).first()

            logger.info(
                "whoop_creds_check",
                user_id=user_id,
                creds_found=creds is not None,
                has_access_token=bool(creds and creds.encrypted_whoop_access_token),
            )

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
        start_date: datetime.date | None = None
        if not full_sync:
            start_date = end_date - datetime.timedelta(days=days)

        sync_type = "full" if full_sync else f"{days}-day"
        logger.info(
            f"Starting Whoop {sync_type} sync for user {user_id}",
            start_date=start_date,
            end_date=end_date,
            full_sync=full_sync,
        )

        recovery_result = sync_whoop_recovery(client, user_id, start_date, end_date)
        sleep_result = sync_whoop_sleep(client, user_id, start_date, end_date)
        workout_result = sync_whoop_workouts(client, user_id, start_date, end_date)
        cycle_result = sync_whoop_cycles(client, user_id, start_date, end_date)

        results = [recovery_result, sleep_result, workout_result, cycle_result]

        summary = {
            "user_id": user_id,
            "sync_date": datetime.datetime.utcnow().isoformat(),
            "sync_type": sync_type,
            "date_range": {
                "start": start_date.isoformat() if start_date else "all",
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
        full_sync = "--full" in sys.argv

        result = sync_whoop_data_for_user(user_id, days, full_sync=full_sync)
        print(f"Sync result: {result}")
    else:
        print("Usage: python pull_whoop_data.py <user_id> [days] [--full]")
