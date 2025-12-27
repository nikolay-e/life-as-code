import datetime
import time
from typing import Any

import requests
from dotenv import load_dotenv
from pydantic import BaseModel

from enums import DataSource, DataType
from logging_config import get_logger
from models import WorkoutSet
from security import decrypt_data_for_user
from sync_manager import extract_and_parse, get_sync_statistics

load_dotenv()

logger = get_logger(__name__)


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
            workout_date = datetime.datetime.fromisoformat(
                workout_data["start_time"].replace("Z", "+00:00")
            ).date()

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
                        logger.warning(f"Error parsing workout set: {e}")
                        continue

        except Exception as e:
            logger.error(f"Error parsing workout data: {e}")

        return workout_sets


class HevyAPIClient:
    """Simplified Heavy API client for sync operations."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.hevyapp.com/v1"
        self.headers = {"api-key": api_key}

    def get_workouts(self, start_date: datetime.date | None = None) -> list[dict]:
        """Fetch workouts from Heavy API with pagination.

        Args:
            start_date: Only return workouts on or after this date. If None, fetch all.
        """
        all_workouts: list[dict] = []
        page = 1
        max_retries = 3

        while True:
            logger.info(f"Fetching Heavy workouts page {page}...")

            params = {"page": page, "pageSize": 10}  # Max 10 per page
            page_success = False

            # Retry logic for transient errors
            for retry in range(max_retries):
                try:
                    response = requests.get(
                        f"{self.base_url}/workouts",
                        headers=self.headers,
                        params=params,
                        timeout=30,
                    )

                    if response.status_code == 200:
                        page_data = response.json()
                        workouts = page_data.get("workouts", [])

                        if not workouts:
                            logger.info("No more workouts found, stopping pagination")
                            return all_workouts

                        # Filter by start_date if provided
                        if start_date:
                            filtered = []
                            oldest_in_page = None
                            for w in workouts:
                                try:
                                    workout_date = datetime.datetime.fromisoformat(
                                        w["start_time"].replace("Z", "+00:00")
                                    ).date()
                                    if (
                                        oldest_in_page is None
                                        or workout_date < oldest_in_page
                                    ):
                                        oldest_in_page = workout_date
                                    if workout_date >= start_date:
                                        filtered.append(w)
                                except (KeyError, ValueError):
                                    filtered.append(w)  # Include if can't parse date
                            workouts = filtered
                            # Stop if all workouts in page are older than start_date
                            if oldest_in_page and oldest_in_page < start_date:
                                logger.info(
                                    f"Reached workouts older than {start_date}, stopping"
                                )
                                all_workouts.extend(workouts)
                                return all_workouts

                        all_workouts.extend(workouts)
                        logger.info(
                            f"Retrieved {len(workouts)} workouts from page {page}"
                        )
                        page_success = True
                        break

                    elif response.status_code == 404:
                        # 404 means no more pages - end of pagination
                        logger.info(
                            f"Page {page} returned 404 - end of data, stopping pagination"
                        )
                        return all_workouts

                    elif response.status_code == 429:
                        # Rate limit - wait and retry
                        logger.warning("Rate limited, waiting 60 seconds...")
                        time.sleep(60)
                        continue

                    else:
                        logger.error(f"HTTP {response.status_code}: {response.text}")
                        if retry == max_retries - 1:
                            raise Exception(f"Failed after {max_retries} retries")

                except requests.exceptions.RequestException as e:
                    logger.warning(f"Request failed (attempt {retry + 1}): {e}")
                    if retry == max_retries - 1:
                        raise

                    # Wait between retries
                    time.sleep(5 * (retry + 1))

            if not page_success:
                logger.error(
                    f"Failed to fetch page {page} after {max_retries} attempts"
                )
                break

            page += 1

            # Safety limit to prevent infinite loops
            if page > 1000:
                logger.warning("Reached maximum page limit (1000)")
                break

        logger.info(f"Total workouts retrieved: {len(all_workouts)}")
        return all_workouts


def sync_hevy_data_for_user(
    user_id: int, days: int = 90, full_sync: bool = False
) -> dict:
    from sqlalchemy import select

    from database import get_db_session_context
    from models import UserCredentials

    try:
        with get_db_session_context() as db:
            creds = db.scalars(
                select(UserCredentials).where(UserCredentials.user_id == user_id)
            ).first()

            if not creds or not creds.encrypted_hevy_api_key:
                return {"error": "No Hevy API key found for user"}

            hevy_api_key = decrypt_data_for_user(creds.encrypted_hevy_api_key, user_id)
    except Exception as e:
        return {"error": f"Failed to get user credentials: {str(e)}"}

    try:
        api_client = HevyAPIClient(hevy_api_key)

        end_date = datetime.date.today()
        start_date: datetime.date | None = None
        if not full_sync:
            start_date = end_date - datetime.timedelta(days=days)

        sync_type = "full" if full_sync else f"{days}-day"
        logger.info(
            f"Starting Hevy {sync_type} sync for user {user_id}",
            start_date=start_date,
            end_date=end_date,
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
            "sync_date": datetime.datetime.utcnow().isoformat(),
            "sync_type": sync_type,
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

        logger.info(f"Hevy sync completed for user {user_id}: {summary}")
        return summary

    except Exception as e:
        error_msg = f"Failed to sync Hevy data for user {user_id}: {str(e)}"
        logger.error(error_msg)
        return {"error": error_msg, "user_id": user_id}


def get_hevy_sync_status(user_id: int) -> dict[str, Any]:
    return get_sync_statistics(user_id, source=DataSource.HEVY)  # type: ignore[no-any-return]


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
