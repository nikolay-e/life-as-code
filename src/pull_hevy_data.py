import datetime

import requests
from dotenv import load_dotenv
from pydantic import BaseModel
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from date_utils import parse_iso_date, utcnow
from enums import DataSource, DataType
from errors import CredentialsDecryptionError, CredentialsNotFoundError
from http_client import RateLimitError
from logging_config import get_logger
from models import WorkoutSet
from sync_manager import (
    extract_and_parse,
    get_provider_credentials,
    get_sync_date_range,
)

load_dotenv()

logger = get_logger(__name__)

MAX_RETRIES = 3
REQUEST_TIMEOUT = 30
RATE_LIMIT_WAIT = 60


class HevyWorkoutData(BaseModel):
    date: datetime.date
    exercise: str
    set_index: int = 0
    weight_kg: float | None = None
    reps: int | None = None
    rpe: float | None = None
    set_type: str | None = None
    duration_seconds: int | None = None
    distance_meters: float | None = None

    @staticmethod
    def _validate_rpe(rpe: float | None) -> float | None:
        if rpe is None:
            return None
        if rpe < 1 or rpe > 10:
            return None
        return rpe

    @staticmethod
    def _validate_reps(reps: int | None) -> int | None:
        if reps is None:
            return None
        if reps < 0:
            return None
        return reps

    @classmethod
    def from_api_response(cls, workout_data: dict) -> list["HevyWorkoutData"]:
        workout_sets = []
        set_counters: dict[tuple, int] = {}

        try:
            workout_date = parse_iso_date(workout_data["start_time"])

            for exercise in workout_data.get("exercises", []):
                exercise_name = exercise.get("title", "Unknown Exercise")

                for set_data in exercise.get("sets", []):
                    try:
                        key = (workout_date, exercise_name)
                        set_index = set_counters.get(key, 0)
                        set_counters[key] = set_index + 1

                        workout_set = cls(
                            date=workout_date,
                            exercise=exercise_name,
                            set_index=set_index,
                            weight_kg=set_data.get("weight_kg"),
                            reps=cls._validate_reps(set_data.get("reps")),
                            rpe=cls._validate_rpe(set_data.get("rpe")),
                            set_type=set_data.get("set_type", "normal"),
                            duration_seconds=set_data.get("duration_seconds"),
                            distance_meters=set_data.get("distance_meters"),
                        )
                        workout_sets.append(workout_set)

                    except Exception as e:
                        logger.warning("hevy_workout_set_parse_error", error=str(e))
                        continue

        except Exception as e:
            logger.error("hevy_workout_data_parse_error", error=str(e))

        return workout_sets


class HevyAPIClient:
    """Hevy API client with tenacity retry logic."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.hevyapp.com/v1"
        self.headers = {"api-key": api_key}

    def _fetch_page(self, page: int) -> requests.Response:
        """Fetch a single page with retry logic via tenacity."""

        @retry(
            stop=stop_after_attempt(MAX_RETRIES),
            wait=wait_exponential(multiplier=1, min=2, max=30),
            retry=retry_if_exception_type((requests.RequestException, RateLimitError)),
            reraise=True,
        )
        def _do_request() -> requests.Response:
            response = requests.get(
                f"{self.base_url}/workouts",
                headers=self.headers,
                params={"page": page, "pageSize": 10},
                timeout=REQUEST_TIMEOUT,
            )

            if response.status_code == 429:
                logger.warning("hevy_rate_limited", wait_seconds=RATE_LIMIT_WAIT)
                raise RateLimitError(RATE_LIMIT_WAIT)

            return response

        result: requests.Response = _do_request()
        return result

    def get_workouts(self, start_date: datetime.date | None = None) -> list[dict]:
        """Fetch workouts from Hevy API with pagination."""
        all_workouts: list[dict] = []
        page = 1
        max_pages = 1000

        while page <= max_pages:
            logger.info("hevy_fetching_page", page=page)

            try:
                response = self._fetch_page(page)

                if response.status_code == 200:
                    page_data = response.json()
                    workouts = page_data.get("workouts", [])

                    if not workouts:
                        logger.info("hevy_pagination_end")
                        break

                    if start_date:
                        filtered = []
                        oldest_in_page = None
                        for w in workouts:
                            try:
                                workout_date = parse_iso_date(w["start_time"])
                                if (
                                    oldest_in_page is None
                                    or workout_date < oldest_in_page
                                ):
                                    oldest_in_page = workout_date
                                if workout_date >= start_date:
                                    filtered.append(w)
                            except (KeyError, ValueError):
                                filtered.append(w)
                        workouts = filtered
                        if oldest_in_page and oldest_in_page < start_date:
                            logger.info("hevy_date_cutoff", cutoff_date=start_date)
                            all_workouts.extend(workouts)
                            break

                    all_workouts.extend(workouts)
                    logger.info(
                        "hevy_page_retrieved", workouts=len(workouts), page=page
                    )

                elif response.status_code == 404:
                    logger.info("hevy_page_not_found", page=page)
                    break

                else:
                    logger.error(
                        "hevy_request_failed",
                        status_code=response.status_code,
                        response=response.text[:200],
                    )
                    break

            except Exception as e:
                logger.error("hevy_fetch_error", page=page, error=str(e))
                break

            page += 1

        logger.info("hevy_fetch_complete", total_workouts=len(all_workouts))
        return all_workouts


def sync_hevy_data_for_user(
    user_id: int, days: int = 90, full_sync: bool = False
) -> dict:
    try:
        creds = get_provider_credentials(user_id, DataSource.HEVY)
    except (CredentialsNotFoundError, CredentialsDecryptionError) as e:
        logger.error("hevy_credentials_error", user_id=user_id, error=str(e))
        return {"error": str(e), "user_id": user_id}

    try:
        api_client = HevyAPIClient(creds.hevy_api_key)
        date_range = get_sync_date_range(days, full_sync)
        start_date = None if full_sync else date_range.start_date

        logger.info(
            "hevy_sync_started",
            user_id=user_id,
            sync_type=date_range.sync_type,
            start_date=start_date,
            end_date=date_range.end_date,
            full_sync=full_sync,
        )

        sync_result = extract_and_parse(
            api_call_func=lambda: api_client.get_workouts(start_date=start_date),
            parser_class=HevyWorkoutData,
            model_class=WorkoutSet,
            unique_fields=["date", "exercise", "set_index"],
            user_id=user_id,
            source=DataSource.HEVY,
            data_type=DataType.WORKOUTS,
        )

        summary = {
            "user_id": user_id,
            "sync_date": utcnow().isoformat(),
            "sync_type": date_range.sync_type,
            "source": "hevy",
            "data_type": "workouts",
            "success": sync_result.success,
            "records_processed": sync_result.records_processed,
            "records_created": sync_result.records_created,
            "records_updated": sync_result.records_updated,
            "records_skipped": sync_result.records_skipped,
            "errors": sync_result.errors[:5],
            "error_count": len(sync_result.errors),
        }

        logger.info(
            "hevy_sync_completed",
            user_id=user_id,
            records_processed=summary["records_processed"],
            records_created=summary["records_created"],
            success=summary["success"],
        )
        return summary

    except Exception as e:
        logger.error("hevy_sync_failed", user_id=user_id, error=str(e))
        return {"error": str(e), "user_id": user_id}


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        user_id = int(sys.argv[1])
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 90
        full_sync = "--full" in sys.argv

        result = sync_hevy_data_for_user(user_id, days, full_sync=full_sync)
        print(f"Sync result: {result}")
    else:
        print("Usage: python pull_hevy_data.py <user_id> [days] [--full]")
