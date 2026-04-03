import datetime
import os
from dataclasses import dataclass
from typing import Any

import requests
from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from database import get_db_session_context
from date_utils import parse_iso_date, utcnow
from enums import DataSource, DataType
from errors import CredentialsDecryptionError, CredentialsNotFoundError
from http_client import AuthenticationError, HTTPClient
from logging_config import get_logger
from models import UserCredentials, WhoopCycle, WhoopRecovery, WhoopSleep, WhoopWorkout
from security import encrypt_data_for_user
from sync_manager import (
    SyncResult,
    UpsertResult,
    get_provider_credentials,
    get_sync_date_range,
    upsert_data,
)
from whoop_schemas import (
    WhoopCycleParser,
    WhoopRecoveryParser,
    WhoopSleepParser,
    WhoopWorkoutParser,
)

load_dotenv()

logger = get_logger(__name__)

MAX_RETRIES = 3
REQUEST_TIMEOUT = 30
RATE_LIMIT_DELAY = 0.6


class WhoopAPIClient:
    def __init__(self, access_token: str, refresh_token: str, user_id: int):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.user_id = user_id
        self.client_id = os.getenv("WHOOP_CLIENT_ID")
        self.client_secret = os.getenv("WHOOP_CLIENT_SECRET")
        self._client = HTTPClient(
            base_url="https://api.prod.whoop.com/developer/v2",
            headers={"Authorization": f"Bearer {self.access_token}"},
            timeout=REQUEST_TIMEOUT,
            max_retries=MAX_RETRIES,
            rate_limit_delay=RATE_LIMIT_DELAY,
        )
        self._oauth_client = HTTPClient(
            base_url="https://api.prod.whoop.com",
            timeout=REQUEST_TIMEOUT,
            max_retries=MAX_RETRIES,
        )

    def _refresh_access_token(self) -> bool:
        try:
            tokens = self._oauth_client.post(
                "oauth/oauth2/token",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self.refresh_token,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
            )

            if not isinstance(tokens, dict) or "access_token" not in tokens:
                logger.error("whoop_token_refresh_failed")
                return False

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
                    creds.whoop_token_expires_at = utcnow() + datetime.timedelta(
                        seconds=tokens.get("expires_in", 3600)
                    )
                    db.commit()

            self._client.session.headers["Authorization"] = (
                f"Bearer {self.access_token}"
            )
            logger.info("whoop_token_refreshed", user_id=self.user_id)
            return True

        except (requests.RequestException, SQLAlchemyError, KeyError, ValueError) as e:
            logger.error("whoop_token_refresh_error", error=str(e))
            return False

    def _make_request(self, endpoint: str, params: dict | None = None) -> dict | None:
        try:
            result = self._client.get(endpoint, params=params)
        except AuthenticationError:
            logger.info("whoop_token_expired")
            if self._refresh_access_token():
                result = self._client.get(endpoint, params=params)
            else:
                logger.error("whoop_api_error", error="Failed to refresh Whoop token")
                return None
        except (requests.RequestException, ValueError, KeyError) as e:
            logger.error("whoop_api_error", error=str(e))
            return None
        if isinstance(result, dict):
            return result
        return None

    def _paginated_request(
        self, endpoint: str, params: dict | None = None, limit: int = 25
    ) -> list[dict]:
        all_records: list[dict] = []
        request_params = dict(params or {})
        request_params["limit"] = limit
        page_count = 0
        max_pages = 1000

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

            if page_count % 10 == 0:
                logger.info(
                    "whoop_pagination_progress",
                    records=len(all_records),
                    pages=page_count,
                )

        logger.info(
            "whoop_pagination_complete", records=len(all_records), pages=page_count
        )
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
                recovery["date"] = parse_iso_date(created_at)
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

            date_obj = parse_iso_date(start_time)
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
                workout["date"] = parse_iso_date(start_time)
                results.append(workout)

        return results

    def get_cycle_data(
        self,
        start_date: datetime.date | None = None,
        end_date: datetime.date | None = None,
    ) -> list[dict]:
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
                date_obj = parse_iso_date(start_time)
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


@dataclass
class WhoopSyncConfig:
    data_type: str
    model_class: type
    parser_class: Any  # Parser class with from_whoop_response method
    unique_fields: list[str]
    get_data_method: str
    parser_needs_date: bool = True


WHOOP_SYNC_CONFIGS = [
    WhoopSyncConfig(
        data_type=DataType.RECOVERY,
        model_class=WhoopRecovery,
        parser_class=WhoopRecoveryParser,
        unique_fields=["date"],
        get_data_method="get_recovery_data",
    ),
    WhoopSyncConfig(
        data_type=DataType.SLEEP,
        model_class=WhoopSleep,
        parser_class=WhoopSleepParser,
        unique_fields=["date"],
        get_data_method="get_sleep_data",
    ),
    WhoopSyncConfig(
        data_type=DataType.WORKOUTS,
        model_class=WhoopWorkout,
        parser_class=WhoopWorkoutParser,
        unique_fields=["date", "start_time"],
        get_data_method="get_workout_data",
        parser_needs_date=False,
    ),
    WhoopSyncConfig(
        data_type=DataType.CYCLES,
        model_class=WhoopCycle,
        parser_class=WhoopCycleParser,
        unique_fields=["date"],
        get_data_method="get_cycle_data",
    ),
]


def _parse_whoop_item(config: WhoopSyncConfig, item: dict):
    if config.parser_needs_date:
        return config.parser_class.from_whoop_response(item, item.get("date"))
    return config.parser_class.from_whoop_response(item)


def _upsert_whoop_item(
    db,
    config: WhoopSyncConfig,
    item: dict,
    user_id: int,
    sync_result: SyncResult,
    counters: dict[str, int],
) -> None:
    try:
        parsed = _parse_whoop_item(config, item)
        if not parsed:
            counters["skipped"] += 1
            return

        data_dict = {
            "user_id": user_id,
            "date": item.get("date"),
            **parsed.model_dump(),
        }

        result, error = upsert_data(
            db, config.model_class, data_dict, config.unique_fields, user_id
        )
        if result == UpsertResult.CREATED:
            counters["created"] += 1
        elif result == UpsertResult.UPDATED:
            counters["updated"] += 1
        else:
            counters["skipped"] += 1
            if error:
                sync_result.add_error(error)
    except (ValueError, KeyError, TypeError, SQLAlchemyError) as e:
        sync_result.add_error(f"Error processing {config.data_type}: {str(e)}")
        counters["skipped"] += 1


def _sync_whoop_data_type(
    client: WhoopAPIClient,
    user_id: int,
    config: WhoopSyncConfig,
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
) -> SyncResult:
    sync_result = SyncResult(
        source=DataSource.WHOOP, data_type=config.data_type, user_id=user_id
    )

    try:
        get_data = getattr(client, config.get_data_method)
        raw_data = get_data(start_date, end_date)
        counters = {"created": 0, "updated": 0, "skipped": 0}

        with get_db_session_context() as db:
            for item in raw_data:
                _upsert_whoop_item(db, config, item, user_id, sync_result, counters)

            db.commit()
            sync_result.records_created = counters["created"]
            sync_result.records_updated = counters["updated"]
            sync_result.records_skipped = counters["skipped"]
            sync_result.success = True

    except (
        requests.RequestException,
        SQLAlchemyError,
        ValueError,
        KeyError,
        TypeError,
    ) as e:
        sync_result.add_error(f"Sync error: {str(e)}")

    return sync_result


def sync_whoop_data_for_user(
    user_id: int, days: int = 90, full_sync: bool = False
) -> dict[str, Any]:
    try:
        creds = get_provider_credentials(user_id, DataSource.WHOOP)
    except (CredentialsNotFoundError, CredentialsDecryptionError) as e:
        logger.error("whoop_credentials_error", user_id=user_id, error=str(e))
        return {"error": str(e), "user_id": user_id}

    if not creds.whoop_access_token or not creds.whoop_refresh_token:
        return {"error": "Whoop tokens not configured", "user_id": user_id}

    try:
        client = WhoopAPIClient(
            creds.whoop_access_token, creds.whoop_refresh_token, user_id
        )
        date_range = get_sync_date_range(days, full_sync)
        start_date = None if full_sync else date_range.start_date
        end_date = date_range.end_date

        logger.info(
            "whoop_sync_started",
            user_id=user_id,
            sync_type=date_range.sync_type,
            start_date=start_date,
            end_date=end_date,
            full_sync=full_sync,
        )

        results = [
            _sync_whoop_data_type(client, user_id, config, start_date, end_date)
            for config in WHOOP_SYNC_CONFIGS
        ]

        summary = {
            "user_id": user_id,
            "sync_date": utcnow().isoformat(),
            "sync_type": date_range.sync_type,
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

        logger.info(
            "whoop_sync_completed",
            user_id=user_id,
            records_processed=summary["total_records_processed"],
            records_created=summary["total_records_created"],
            success=summary["success"],
        )
        return summary

    except Exception as e:  # catch-all for sync resilience
        logger.error("whoop_sync_failed", user_id=user_id, error=str(e))
        return {"error": str(e), "user_id": user_id}


def refresh_whoop_token_for_user(user_id: int) -> bool:
    try:
        creds = get_provider_credentials(user_id, DataSource.WHOOP)
    except (CredentialsNotFoundError, CredentialsDecryptionError) as e:
        logger.error("whoop_credentials_error", user_id=user_id, error=str(e))
        return False

    if not creds.whoop_access_token or not creds.whoop_refresh_token:
        return False

    try:
        client = WhoopAPIClient(
            creds.whoop_access_token, creds.whoop_refresh_token, user_id
        )
        return client._refresh_access_token()
    except (requests.RequestException, SQLAlchemyError, ValueError, KeyError) as e:
        logger.error("whoop_token_refresh_failed", user_id=user_id, error=str(e))
        return False


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
