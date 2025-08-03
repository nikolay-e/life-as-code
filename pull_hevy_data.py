"""
Hevy Workout Data Extractor - Database Version
Extracts workout data from Hevy API and stores it in PostgreSQL database.
"""

import logging
import time

import pandas as pd
import requests
from dotenv import load_dotenv
from sqlalchemy import func, select

from database import SessionLocal, get_db_session_context
from models import DataSync, User, UserCredentials, WorkoutSet
from security import decrypt_data_for_user

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_all_workouts(api_key):
    """
    Fetches all workouts from the Hevy API by handling pagination.
    Returns a list of workout records.
    """
    all_workouts = []
    page = 1

    while True:
        logger.info(f"Fetching page {page}...")

        headers = {"api-key": api_key}
        params = {"page": page, "pageSize": 10}  # Max 10 per page

        # Retry logic for transient errors
        max_retries = 3
        page_success = False

        for retry in range(max_retries):
            try:
                response = requests.get(
                    "https://api.hevy.com/v1/workouts",
                    headers=headers,
                    params=params,
                    timeout=30,
                )

                if response.status_code == 404:
                    # End of data - this is normal when we've fetched all pages
                    logger.info(f"Reached end of data at page {page}")
                    return all_workouts

                if response.status_code != 200:
                    raise Exception(
                        f"Error fetching data: {response.status_code} {response.text}"
                    )

                data = response.json()
                workouts_on_page = data.get("workouts", [])

                if not workouts_on_page:
                    # No more workouts, return all collected data
                    return all_workouts

                all_workouts.extend(workouts_on_page)
                logger.info(
                    f"Fetched {len(workouts_on_page)} workouts from page {page}"
                )
                page += 1
                page_success = True
                break  # Success, move to next page

            except Exception as e:
                if retry < max_retries - 1:
                    wait_time = 2**retry
                    logger.warning(
                        f"Error fetching page {page}, retrying in {wait_time}s (attempt {retry + 1}/{max_retries}): {e}"
                    )
                    time.sleep(wait_time)
                else:
                    logger.error(
                        f"Failed to fetch page {page} after {max_retries} retries: {e}"
                    )
                    raise

        if not page_success:
            logger.error(f"Failed to fetch page {page}")
            break

    logger.info(f"\n📊 Total workouts fetched: {len(all_workouts)}")
    return all_workouts


def sync_hevy_data(user_id: int):
    """
    Fetches all workouts from Hevy for a specific user and stores them in the database.
    Returns a summary of the sync operation.
    """
    logger.info(f"🏋️ Starting Hevy workout data sync for user_id: {user_id}")

    # Get user credentials from database
    db = SessionLocal()
    try:
        user = db.get(User, user_id)
        creds = db.scalars(select(UserCredentials).filter_by(user_id=user_id)).first()

        if not user or not creds or not creds.encrypted_hevy_api_key:
            raise ValueError(
                "Hevy API key not set for this user. Please update your credentials in Settings."
            )

        # Decrypt API key
        try:
            api_key = decrypt_data_for_user(creds.encrypted_hevy_api_key, user_id)
        except Exception as e:
            logger.error(f"Failed to decrypt Hevy API key for user {user_id}: {e}")
            return {
                "error": "Invalid credentials encryption. Please reset your Hevy API key in settings."
            }
        logger.info("Using encrypted Hevy API key")

    finally:
        db.close()

    # Fetch all workouts
    try:
        all_workouts = get_all_workouts(api_key)
    except Exception as e:
        logger.error(f"Failed to fetch workouts: {e}")
        return {"error": str(e)}

    if not all_workouts:
        logger.info("No workouts found.")
        return {"total": 0, "new": 0, "skipped": 0}

    # Process workouts and store in database
    sync_results = {"total": 0, "new": 0, "skipped": 0, "errors": 0}

    with get_db_session_context() as db:
        # Get existing workout sets to avoid duplicates (allow multiple workouts per day)
        existing_sets = set()
        existing_records = db.execute(
            select(
                WorkoutSet.date,
                WorkoutSet.exercise,
                WorkoutSet.weight_kg,
                WorkoutSet.reps,
            ).filter(WorkoutSet.user_id == user_id)
        ).all()

        for record in existing_records:
            # Create a key that uniquely identifies a set
            set_key = (record.date, record.exercise, record.weight_kg, record.reps)
            existing_sets.add(set_key)

        for workout in all_workouts:
            try:
                workout_date = pd.to_datetime(workout["start_time"]).date()
                workout_processed = False

                # Process each exercise in the workout
                for exercise in workout.get("exercises", []):
                    exercise_title = exercise.get("title", "Unknown")

                    for set_data in exercise.get("sets", []):
                        weight_kg = set_data.get("weight_kg")
                        reps = set_data.get("reps")

                        # Check if this specific set already exists
                        set_key = (workout_date, exercise_title, weight_kg, reps)
                        if set_key in existing_sets:
                            sync_results["skipped"] += 1
                            continue

                        new_set = WorkoutSet(
                            user_id=user_id,
                            date=workout_date,
                            exercise=exercise_title,
                            weight_kg=weight_kg,
                            reps=reps,
                            rpe=set_data.get("rpe"),
                            set_type=set_data.get("set_type", "normal"),
                            duration_seconds=set_data.get("duration_seconds"),
                            distance_meters=set_data.get("distance_meters"),
                        )
                        db.add(new_set)
                        sync_results["new"] += 1
                        workout_processed = True

                        # Add to existing sets to avoid duplicates in this session
                        existing_sets.add(set_key)

                if workout_processed:
                    sync_results["total"] += 1

            except Exception as e:
                logger.error(f"Error processing workout: {e}")
                sync_results["errors"] += 1

        # Update sync tracking
        sync_record = DataSync(
            user_id=user_id,
            source="hevy",
            data_type="workouts",
            last_sync_date=pd.Timestamp.now().date(),
            records_synced=sync_results["new"],
            status="success" if sync_results["errors"] == 0 else "partial",
            error_message=(
                f"{sync_results['errors']} errors"
                if sync_results["errors"] > 0
                else None
            ),
        )
        db.merge(sync_record)  # Use merge to update existing or create new

    logger.info("✅ Hevy workout data sync completed!")
    logger.info(f"  📈 {sync_results['new']} new sets added")
    logger.info(f"  ⏭️ {sync_results['skipped']} dates skipped (already exist)")
    if sync_results["errors"] > 0:
        logger.warning(f"  ⚠️ {sync_results['errors']} errors encountered")

    # Print workout summary
    with get_db_session_context() as db:
        total_sets = db.scalar(select(func.count()).select_from(WorkoutSet))
        unique_exercises = db.scalar(select(func.count(WorkoutSet.exercise.distinct())))
        date_range = db.execute(
            select(func.min(WorkoutSet.date), func.max(WorkoutSet.date))
        ).first()

        logger.info("\n🏋️ Workout Database Summary:")
        logger.info(f"  - Total sets: {total_sets}")
        logger.info(f"  - Unique exercises: {unique_exercises}")
        if date_range[0] and date_range[1]:
            logger.info(f"  - Date range: {date_range[0]} to {date_range[1]}")

    return sync_results


if __name__ == "__main__":
    print("🏋️ HEVY WORKOUT DATA EXTRACTOR (Multi-User)")
    print("Extracts workout data from Hevy API and stores it in PostgreSQL database.")
    print("Note: This script now requires user authentication.")
    print("Use the web portal Settings page to sync data instead.")
    print()

    print("For testing purposes, you can still run this with a user ID:")
    user_id_input = input("Enter user ID to sync (or press Enter to exit): ")

    if not user_id_input:
        print("Exiting...")
        exit(0)

    try:
        user_id = int(user_id_input)
        results = sync_hevy_data(user_id=user_id)

        if "error" not in results:
            print(
                f"\n🎉 Sync completed! Added {results['new']} new workout sets to database."
            )
            print(
                f"Total: {results['total']}, Skipped: {results.get('skipped', 0)}, Errors: {results.get('errors', 0)}"
            )
        else:
            print(f"❌ Sync failed: {results['error']}")
            exit(1)

    except ValueError:
        print("❌ Invalid user ID. Please enter a number.")
        exit(1)
    except Exception as e:
        logger.error(f"❌ Sync failed: {e}")
        exit(1)
