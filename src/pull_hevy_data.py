"""
Hevy Workout Data Extractor - Refactored with Sync Manager
Extracts workout data from Hevy API and stores it in PostgreSQL database.
"""

import datetime
import logging
from typing import Any

import requests
from dotenv import load_dotenv
from pydantic import BaseModel

from models import WorkoutSet
from security import decrypt_data_for_user
from sync_manager import extract_and_parse, get_sync_statistics

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class HevyWorkoutData(BaseModel):
    """Pydantic model for Hevy workout data."""

    date: datetime.date
    exercise: str
    weight_kg: float | None = None
    reps: int | None = None
    rpe: float | None = None
    set_type: str | None = None
    duration_seconds: int | None = None
    distance_meters: float | None = None

    @classmethod
    def from_api_response(cls, workout_data: dict) -> list["HevyWorkoutData"]:
        """Convert Hevy API workout response to HevyWorkoutData instances."""
        workout_sets = []

        try:
            # Extract workout date
            workout_date = datetime.datetime.fromisoformat(
                workout_data["start_time"].replace("Z", "+00:00")
            ).date()

            # Process each exercise in the workout
            for exercise in workout_data.get("exercises", []):
                exercise_name = exercise.get("title", "Unknown Exercise")

                # Process each set in the exercise
                for set_data in exercise.get("sets", []):
                    try:
                        workout_set = cls(
                            date=workout_date,
                            exercise=exercise_name,
                            weight_kg=set_data.get("weight_kg"),
                            reps=set_data.get("reps"),
                            rpe=set_data.get("rpe"),
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
    """Simplified Hevy API client for sync operations."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.hevy.com/v1"
        self.headers = {"api-key": api_key}

    def get_workouts(self) -> list[dict]:
        """Fetch all workouts from Hevy API with pagination."""
        all_workouts: list[dict] = []
        page = 1
        max_retries = 3

        while True:
            logger.info(f"Fetching Hevy workouts page {page}...")

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

                        all_workouts.extend(workouts)
                        logger.info(
                            f"Retrieved {len(workouts)} workouts from page {page}"
                        )
                        page_success = True
                        break

                    elif response.status_code == 429:
                        # Rate limit - wait and retry
                        logger.warning("Rate limited, waiting 60 seconds...")
                        import time

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
                    import time

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


def sync_hevy_data_for_user(user_id: int) -> dict:
    """
    Main function to sync Hevy workout data for a user using the sync manager.

    Args:
        user_id: User ID to sync data for

    Returns:
        dict: Summary of sync results
    """
    from sqlalchemy import select

    from database import get_db_session_context
    from models import UserCredentials

    # Get user credentials
    try:
        with get_db_session_context() as db:
            creds = db.scalars(
                select(UserCredentials).where(UserCredentials.user_id == user_id)
            ).first()

            if not creds or not creds.encrypted_hevy_api_key:
                return {"error": "No Hevy API key found for user"}

            # Decrypt API key
            hevy_api_key = decrypt_data_for_user(creds.encrypted_hevy_api_key, user_id)
    except Exception as e:
        return {"error": f"Failed to get user credentials: {str(e)}"}

    try:
        # Initialize Hevy API client
        api_client = HevyAPIClient(hevy_api_key)

        # Use the sync manager to extract and parse data
        sync_result = extract_and_parse(
            api_call_func=api_client.get_workouts,
            parser_class=HevyWorkoutData,
            model_class=WorkoutSet,
            unique_fields=["date", "exercise"],  # Unique by date and exercise
            user_id=user_id,
            source="hevy",
            data_type="workouts",
        )

        # Compile summary
        summary = {
            "user_id": user_id,
            "sync_date": datetime.datetime.utcnow().isoformat(),
            "source": "hevy",
            "data_type": "workouts",
            "success": sync_result.success,
            "records_processed": sync_result.records_processed,
            "records_created": sync_result.records_created,
            "records_updated": sync_result.records_updated,
            "records_skipped": sync_result.records_skipped,
            "errors": sync_result.errors[:5],  # First 5 errors only
            "error_count": len(sync_result.errors),
        }

        logger.info(f"Hevy sync completed for user {user_id}: {summary}")
        return summary

    except Exception as e:
        error_msg = f"Failed to sync Hevy data for user {user_id}: {str(e)}"
        logger.error(error_msg)
        return {"error": error_msg, "user_id": user_id}


def get_hevy_sync_status(user_id: int) -> dict[str, Any]:
    """Get sync status for Hevy data."""
    return get_sync_statistics(user_id, source="hevy")  # type: ignore[no-any-return]


if __name__ == "__main__":
    # Example usage
    import sys

    if len(sys.argv) > 1:
        user_id = int(sys.argv[1])
        result = sync_hevy_data_for_user(user_id)
        print(f"Sync result: {result}")
    else:
        print("Usage: python pull_hevy_data.py <user_id>")
