"""
Garmin Connect Data Extractor - Database Version
Extracts health data from Garmin Connect and stores it in PostgreSQL database.
"""

import datetime
import logging
import os

from dotenv import load_dotenv
from garminconnect import Garmin, GarminConnectAuthenticationError
from garth.exc import GarthHTTPError
from sqlalchemy import select

from database import SessionLocal, get_db_session_context
from models import (
    HRV,
    DataSync,
    HeartRate,
    Sleep,
    Stress,
    User,
    UserCredentials,
    Weight,
)
from security import decrypt_data

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init_api(email: str, password: str, user_id: int):
    """Initialize Garmin API with proper authentication using provided credentials."""
    # User-specific token storage to prevent cross-user data bleed
    tokenstore_dir = os.path.expanduser(f"~/.garminconnect/user_{user_id}")
    tokenstore = os.path.join(tokenstore_dir, "tokens")
    os.makedirs(tokenstore_dir, exist_ok=True)

    try:
        logger.info(f"Trying to login using tokens from '{tokenstore}'...")
        garmin = Garmin()
        garmin.login(tokenstore)

        # Ensure display_name is set after login
        if not hasattr(garmin, "display_name") or garmin.display_name is None:
            logger.warning("Display name not set after login, fetching user profile...")
            # Try to get the display name from the user profile
            try:
                profile = garmin.garth.profile
                if profile and "displayName" in profile:
                    garmin.display_name = profile["displayName"]
                    logger.info(f"Display name set from profile: {garmin.display_name}")
                else:
                    # If profile doesn't have displayName, try getting full name
                    full_name = garmin.get_full_name()
                    if full_name:
                        garmin.display_name = full_name.replace(" ", "")
                        logger.info(
                            f"Display name set from full name: {garmin.display_name}"
                        )
            except Exception as e:
                logger.error(f"Failed to set display name: {e}")
                # As a last resort, try to extract from email
                if email:
                    garmin.display_name = email.split("@")[0]
                    logger.warning(
                        f"Using email prefix as display name: {garmin.display_name}"
                    )

        logger.info(
            f"Successfully logged in as: {getattr(garmin, 'display_name', 'Unknown')}"
        )
        return garmin
    except (FileNotFoundError, GarthHTTPError, GarminConnectAuthenticationError) as e:
        logger.info("Login tokens not present, logging in with credentials...")

        if not email or not password:
            raise ValueError(
                "Email and password are required for Garmin authentication"
            ) from e

        try:
            garmin = Garmin(
                email=email, password=password, is_cn=False, return_on_mfa=True
            )
            result1, result2 = garmin.login()

            if result1 == "needs_mfa":
                logger.error(
                    "MFA authentication required but not supported in multi-user mode"
                )
                return {
                    "error": "MFA authentication required. Please use manual sync or contact support for alternative authentication methods."
                }

            garmin.garth.dump(tokenstore_dir)

            # Ensure display_name is set after login
            if not hasattr(garmin, "display_name") or garmin.display_name is None:
                logger.warning(
                    "Display name not set after login, fetching user profile..."
                )
                try:
                    profile = garmin.garth.profile
                    if profile and "displayName" in profile:
                        garmin.display_name = profile["displayName"]
                        logger.info(
                            f"Display name set from profile: {garmin.display_name}"
                        )
                    else:
                        # If profile doesn't have displayName, try getting full name
                        full_name = garmin.get_full_name()
                        if full_name:
                            garmin.display_name = full_name.replace(" ", "")
                            logger.info(
                                f"Display name set from full name: {garmin.display_name}"
                            )
                except Exception as e:
                    logger.error(f"Failed to set display name: {e}")
                    # As a last resort, use email prefix
                    if email:
                        garmin.display_name = email.split("@")[0]
                        logger.warning(
                            f"Using email prefix as display name: {garmin.display_name}"
                        )

            logger.info(
                f"✅ Successfully authenticated with Garmin Connect as: {getattr(garmin, 'display_name', 'Unknown')}"
            )
            return garmin

        except Exception as e:
            logger.error(f"❌ Authentication failed: {e}")
            raise


def extract_sleep_data(
    api: Garmin, date_str: str, target_date: datetime.date, user_id: int
) -> Sleep | None:
    """Extract sleep data for a specific date and user."""
    try:
        sleep_data = api.get_sleep_data(date_str)
        if not sleep_data or not sleep_data.get("dailySleepDTO"):
            return None

        sleep_dto = sleep_data["dailySleepDTO"]

        return Sleep(
            user_id=user_id,
            date=target_date,
            deep_minutes=sleep_dto.get("deepSleepSeconds", 0) / 60,
            light_minutes=sleep_dto.get("lightSleepSeconds", 0) / 60,
            rem_minutes=sleep_dto.get("remSleepSeconds", 0) / 60,
            awake_minutes=sleep_dto.get("awakeSleepSeconds", 0) / 60,
            total_sleep_minutes=sleep_dto.get("sleepTimeSeconds", 0) / 60,
            sleep_score=sleep_dto.get("sleepScores", {})
            .get("overall", {})
            .get("value"),
        )

    except Exception as e:
        logger.warning(f"Failed to extract sleep data for {date_str}: {e}")
        return None


def extract_hrv_data(
    api: Garmin, date_str: str, target_date: datetime.date, user_id: int
) -> HRV | None:
    """Extract HRV data for a specific date and user, trying multiple formats."""
    try:
        hrv_data = api.get_hrv_data(date_str)
        # Log raw data to understand the format
        logger.debug(f"HRV data received for {date_str}")

        if not hrv_data:
            return None

        hrv_avg = None
        hrv_status = "unknown"

        # Try format 1: Nested under 'hrvStatusSummary' (common)
        if "hrvStatusSummary" in hrv_data and hrv_data["hrvStatusSummary"]:
            summary = hrv_data["hrvStatusSummary"]
            if summary.get("status") != "NO_DATA":
                hrv_avg = summary.get("lastNightAvg")
                hrv_status = summary.get("status", "unknown").lower()

        # Try format 2: A simple list of values (less common)
        elif isinstance(hrv_data, list) and hrv_data:
            hrv_avg = hrv_data[0].get("lastNightAvg")

        # Try format 3: Top-level keys (older format)
        elif isinstance(hrv_data, dict) and hrv_avg is None:
            hrv_avg = hrv_data.get("lastNightAvg") or hrv_data.get("hrvValue")

        if hrv_avg is not None:
            logger.info(f"Successfully extracted HRV value for {date_str}: {hrv_avg}")
            return HRV(
                user_id=user_id,
                date=target_date,
                hrv_avg=float(hrv_avg),
                hrv_status=hrv_status,
            )

        logger.warning(f"Could not extract HRV from response for {date_str}")
        return None

    except Exception as e:
        logger.error(f"Failed to process HRV data for {date_str}: {e}")
        return None


def extract_weight_data(
    api: Garmin, date_str: str, target_date: datetime.date, user_id: int
) -> Weight | None:
    """Extract weight and body composition data for a specific date and user."""
    try:
        # Use get_daily_weigh_ins which is more reliable for single days
        weight_data = api.get_daily_weigh_ins(date_str)
        logger.debug(f"Weight data received for {date_str}")
        if not weight_data:
            logger.info(f"No weight data found for {date_str}")
            return None

        # The structure is simpler with this endpoint
        weight_value = weight_data.get("weight")
        if weight_value and weight_value > 500:  # Convert from grams if needed
            weight_value /= 1000

        return Weight(
            user_id=user_id,
            date=target_date,
            weight_kg=weight_value,
            bmi=weight_data.get("bmi"),
            body_fat_pct=weight_data.get("bodyFat"),
            muscle_mass_kg=(
                weight_data.get("muscleMass", 0) / 1000
                if weight_data.get("muscleMass")
                else None
            ),
            bone_mass_kg=(
                weight_data.get("boneMass", 0) / 1000
                if weight_data.get("boneMass")
                else None
            ),
            water_pct=weight_data.get("bodyWater"),
        )

    except Exception as e:
        logger.warning(f"Failed to extract weight data for {date_str}: {e}")
        logger.exception("Full weight exception details:")
        return None


def extract_heart_rate_data(
    api: Garmin, date_str: str, target_date: datetime.date, user_id: int
) -> HeartRate | None:
    """Extract heart rate data for a specific date and user."""
    try:
        # The get_heart_rates method might need the username
        # Try to get the heart rate data
        hr_data = api.get_heart_rates(date_str)
        if not hr_data:
            return None

        return HeartRate(
            user_id=user_id,
            date=target_date,
            resting_hr=hr_data.get("restingHeartRate"),
            max_hr=hr_data.get("maxHeartRate"),
            avg_hr=hr_data.get("averageHeartRate"),
        )

    except Exception as e:
        logger.warning(f"Failed to extract heart rate data for {date_str}: {e}")
        return None


def extract_stress_data(
    api: Garmin, date_str: str, target_date: datetime.date, user_id: int
) -> Stress | None:
    """Extract stress data for a specific date and user."""
    try:
        stress_data = api.get_stress_data(date_str)
        logger.debug(f"Stress data received for {date_str}")
        if not stress_data:
            return None

        # Try to extract stress values from various possible formats
        avg_stress = None
        max_stress = None
        stress_level = "unknown"
        rest_stress = None
        activity_stress = None

        # Format 1: Check if it's a dict with stress values
        if isinstance(stress_data, dict):
            avg_stress = stress_data.get("averageStressLevel")
            max_stress = stress_data.get("maxStressLevel")
            rest_stress = stress_data.get("restStressAverage")
            activity_stress = stress_data.get("activityStressAverage")

            # Determine stress level based on average
            if avg_stress:
                if avg_stress < 25:
                    stress_level = "low"
                elif avg_stress < 50:
                    stress_level = "medium"
                else:
                    stress_level = "high"

        # Format 2: Check if it has stress chart data
        elif isinstance(stress_data, list) and stress_data:
            # Take average of available stress readings
            stress_values = [
                item.get("stressLevel")
                for item in stress_data
                if item.get("stressLevel")
            ]
            if stress_values:
                avg_stress = sum(stress_values) / len(stress_values)
                max_stress = max(stress_values)

        if avg_stress is not None:
            logger.info(
                f"Successfully extracted stress data for {date_str}: avg={avg_stress}"
            )
            return Stress(
                user_id=user_id,
                date=target_date,
                avg_stress=avg_stress,
                max_stress=max_stress,
                stress_level=stress_level,
                rest_stress=rest_stress,
                activity_stress=activity_stress,
            )

        logger.warning(f"Could not extract stress from response for {date_str}")
        return None

    except Exception as e:
        logger.error(f"Failed to process stress data for {date_str}: {e}")
        return None


def sync_garmin_data(user_id: int, days: int = 60) -> dict:
    """
    Sync Garmin data for a specific user for the specified number of days.
    Returns a summary of the sync operation.
    """
    logger.info(
        f"🏥 Starting Garmin data sync for user_id: {user_id}, last {days} days"
    )

    # Get user credentials from database
    db = SessionLocal()
    try:
        user = db.get(User, user_id)
        creds = db.scalars(select(UserCredentials).filter_by(user_id=user_id)).first()

        if not user or not creds or not creds.encrypted_garmin_password:
            raise ValueError(
                "Garmin credentials not set for this user. Please update your credentials in Settings."
            )

        # Decrypt credentials
        email = creds.garmin_email or user.username
        try:
            password = decrypt_data(creds.encrypted_garmin_password)
        except Exception as e:
            logger.error(f"Failed to decrypt Garmin password for user {user_id}: {e}")
            return {
                "error": "Invalid credentials encryption. Please reset your Garmin credentials in settings."
            }

        logger.info(f"Using Garmin account: {email}")

    finally:
        db.close()

    # Initialize API
    try:
        api_result = init_api(email, password, user_id)
        if isinstance(api_result, dict) and "error" in api_result:
            # Handle MFA or other errors
            error_msg = api_result["error"]
            logger.error(f"API initialization error for user {user_id}: {error_msg}")

            # Store error in database
            with get_db_session_context() as db:
                sync_record = DataSync(
                    user_id=user_id,
                    source="garmin",
                    data_type="all",
                    last_sync_date=datetime.date.today(),
                    records_synced=0,
                    status="error",
                    error_message=error_msg,
                )
                db.add(sync_record)

            return api_result

        api = api_result

        # Double-check that api is not an error dict after assignment
        if isinstance(api, dict) and "error" in api:
            return api

    except GarminConnectAuthenticationError as e:
        # Handle MFA error specifically
        error_msg = str(e)
        logger.error(f"Authentication error for user {user_id}: {error_msg}")

        # Store error in database
        with get_db_session_context() as db:
            sync_record = DataSync(
                user_id=user_id,
                source="garmin",
                data_type="all",
                last_sync_date=datetime.date.today(),
                records_synced=0,
                status="error",
                error_message=error_msg,
            )
            db.add(sync_record)

        return {"error": error_msg, "type": "authentication"}
    except Exception as e:
        # Handle other errors
        error_msg = f"Failed to initialize Garmin API: {str(e)}"
        logger.error(error_msg)

        # Store error in database
        with get_db_session_context() as db:
            sync_record = DataSync(
                user_id=user_id,
                source="garmin",
                data_type="all",
                last_sync_date=datetime.date.today(),
                records_synced=0,
                status="error",
                error_message=error_msg,
            )
            db.add(sync_record)

        return {"error": error_msg, "type": "general"}

    # Date range
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=days)

    # Track sync results
    sync_results = {
        "sleep": {"total": 0, "new": 0, "updated": 0, "errors": 0},
        "hrv": {"total": 0, "new": 0, "updated": 0, "errors": 0},
        "weight": {"total": 0, "new": 0, "updated": 0, "errors": 0},
        "heart_rate": {"total": 0, "new": 0, "updated": 0, "errors": 0},
        "stress": {"total": 0, "new": 0, "updated": 0, "errors": 0},
    }

    with get_db_session_context() as db:
        current_date = start_date

        while current_date <= end_date:
            date_str = current_date.strftime("%Y-%m-%d")
            logger.info(f"Processing {date_str}...")

            # Extract and save sleep data
            try:
                sleep_data = extract_sleep_data(api, date_str, current_date, user_id)
                if sleep_data:
                    existing = db.scalars(
                        select(Sleep).filter(
                            Sleep.user_id == user_id, Sleep.date == current_date
                        )
                    ).first()
                    if existing:
                        # Check if data has changed before updating
                        has_changes = False
                        for attr in [
                            "deep_minutes",
                            "light_minutes",
                            "rem_minutes",
                            "awake_minutes",
                            "total_sleep_minutes",
                            "sleep_score",
                        ]:
                            if (
                                hasattr(sleep_data, attr)
                                and getattr(sleep_data, attr) is not None
                                and getattr(existing, attr) != getattr(sleep_data, attr)
                            ):
                                setattr(existing, attr, getattr(sleep_data, attr))
                                has_changes = True

                        if has_changes:
                            sync_results["sleep"]["updated"] += 1
                        else:
                            sync_results["sleep"]["unchanged"] = (
                                sync_results["sleep"].get("unchanged", 0) + 1
                            )
                    else:
                        db.add(sleep_data)
                        sync_results["sleep"]["new"] += 1
                    sync_results["sleep"]["total"] += 1
            except Exception as e:
                logger.error(f"Error processing sleep data for {date_str}: {e}")
                sync_results["sleep"]["errors"] += 1

            # Extract and save HRV data
            try:
                hrv_data = extract_hrv_data(api, date_str, current_date, user_id)
                if hrv_data:
                    existing = db.scalars(
                        select(HRV).filter(
                            HRV.user_id == user_id, HRV.date == current_date
                        )
                    ).first()
                    if existing:
                        # Check if data has changed before updating
                        has_changes = False
                        if existing.hrv_avg != hrv_data.hrv_avg:
                            existing.hrv_avg = hrv_data.hrv_avg
                            has_changes = True
                        if existing.hrv_status != hrv_data.hrv_status:
                            existing.hrv_status = hrv_data.hrv_status
                            has_changes = True

                        if has_changes:
                            sync_results["hrv"]["updated"] += 1
                        else:
                            sync_results["hrv"]["unchanged"] = (
                                sync_results["hrv"].get("unchanged", 0) + 1
                            )
                    else:
                        db.add(hrv_data)
                        sync_results["hrv"]["new"] += 1
                    sync_results["hrv"]["total"] += 1
            except Exception as e:
                logger.error(f"Error processing HRV data for {date_str}: {e}")
                sync_results["hrv"]["errors"] += 1

            # Extract and save weight data
            try:
                weight_data = extract_weight_data(api, date_str, current_date, user_id)
                if weight_data:
                    # Weight entries - check if we have any entry for this date
                    existing = db.scalars(
                        select(Weight).filter(
                            Weight.user_id == user_id,
                            Weight.date == current_date,
                        )
                    ).first()

                    if existing:
                        # Check if data has changed before updating
                        has_changes = False
                        for attr in [
                            "weight_kg",
                            "bmi",
                            "body_fat_pct",
                            "muscle_mass_kg",
                            "bone_mass_kg",
                            "water_pct",
                        ]:
                            if (
                                hasattr(weight_data, attr)
                                and getattr(weight_data, attr) is not None
                                and getattr(existing, attr)
                                != getattr(weight_data, attr)
                            ):
                                setattr(existing, attr, getattr(weight_data, attr))
                                has_changes = True

                        if has_changes:
                            sync_results["weight"]["updated"] += 1
                        else:
                            sync_results["weight"]["unchanged"] = (
                                sync_results["weight"].get("unchanged", 0) + 1
                            )
                    else:
                        db.add(weight_data)
                        sync_results["weight"]["new"] += 1
                    sync_results["weight"]["total"] += 1
            except Exception as e:
                logger.error(f"Error processing weight data for {date_str}: {e}")
                sync_results["weight"]["errors"] += 1

            # Extract and save heart rate data
            try:
                hr_data = extract_heart_rate_data(api, date_str, current_date, user_id)
                if hr_data:
                    existing = db.scalars(
                        select(HeartRate).filter(
                            HeartRate.user_id == user_id, HeartRate.date == current_date
                        )
                    ).first()
                    if existing:
                        # Check if data has changed before updating
                        has_changes = False
                        for attr in ["resting_hr", "max_hr", "avg_hr"]:
                            if (
                                hasattr(hr_data, attr)
                                and getattr(hr_data, attr) is not None
                                and getattr(existing, attr) != getattr(hr_data, attr)
                            ):
                                setattr(existing, attr, getattr(hr_data, attr))
                                has_changes = True

                        if has_changes:
                            sync_results["heart_rate"]["updated"] += 1
                        else:
                            sync_results["heart_rate"]["unchanged"] = (
                                sync_results["heart_rate"].get("unchanged", 0) + 1
                            )
                    else:
                        db.add(hr_data)
                        sync_results["heart_rate"]["new"] += 1
                    sync_results["heart_rate"]["total"] += 1
            except Exception as e:
                logger.error(f"Error processing heart rate data for {date_str}: {e}")
                sync_results["heart_rate"]["errors"] += 1

            # Extract and save stress data
            try:
                stress_data = extract_stress_data(api, date_str, current_date, user_id)
                if stress_data:
                    existing = db.scalars(
                        select(Stress).filter(
                            Stress.user_id == user_id, Stress.date == current_date
                        )
                    ).first()
                    if existing:
                        # Update existing record
                        has_changes = False
                        for attr in [
                            "avg_stress",
                            "max_stress",
                            "stress_level",
                            "rest_stress",
                            "activity_stress",
                        ]:
                            if (
                                hasattr(stress_data, attr)
                                and getattr(stress_data, attr) is not None
                                and getattr(existing, attr)
                                != getattr(stress_data, attr)
                            ):
                                setattr(existing, attr, getattr(stress_data, attr))
                                has_changes = True

                        if has_changes:
                            sync_results["stress"]["updated"] += 1
                        else:
                            sync_results["stress"]["unchanged"] = (
                                sync_results["stress"].get("unchanged", 0) + 1
                            )
                    else:
                        db.add(stress_data)
                        sync_results["stress"]["new"] += 1
                    sync_results["stress"]["total"] += 1
            except Exception as e:
                logger.error(f"Error processing stress data for {date_str}: {e}")
                sync_results["stress"]["errors"] += 1

            current_date += datetime.timedelta(days=1)

            # Small delay to avoid rate limiting
            import time

            time.sleep(1.0)  # Increase to prevent rate limiting

        # Update sync tracking
        for data_type in sync_results.keys():
            sync_record = DataSync(
                user_id=user_id,
                source="garmin",
                data_type=data_type,
                last_sync_date=end_date,
                records_synced=sync_results[data_type]["total"],
                status=(
                    "success" if sync_results[data_type]["errors"] == 0 else "partial"
                ),
                error_message=(
                    f"{sync_results[data_type]['errors']} errors"
                    if sync_results[data_type]["errors"] > 0
                    else None
                ),
            )
            db.merge(sync_record)  # Use merge to update existing or create new

    logger.info("✅ Garmin data sync completed successfully!")

    # Print summary
    for data_type, results in sync_results.items():
        logger.info(
            f"  {data_type}: {results['new']} new, {results['updated']} updated, {results['errors']} errors"
        )

    return sync_results


if __name__ == "__main__":
    print("🏥 GARMIN CONNECT DATA EXTRACTOR (Multi-User)")
    print("Extracts health data and stores it in PostgreSQL database.")
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
        days = int(input("Enter number of days to sync (default 60): ") or "60")

        results = sync_garmin_data(user_id=user_id, days=days)

        print("\n" + "=" * 50)
        print("📊 SYNC SUMMARY")
        print("=" * 50)

        for data_type, stats in results.items():
            print(
                f"{data_type.upper()}: {stats['new']} new, {stats['updated']} updated, {stats['errors']} errors"
            )

        print("\n✅ Sync completed successfully!")

    except ValueError:
        print("❌ Invalid user ID. Please enter a number.")
        exit(1)
    except Exception as e:
        print(f"\n❌ Sync failed: {e}")
        exit(1)
