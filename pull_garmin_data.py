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
from garmin_schemas import (
    GarminHRVData,
    GarminSleepData,
    GarminStepsData,
    GarminStressData,
)
from models import (
    HRV,
    DataSync,
    HeartRate,
    Sleep,
    Steps,
    Stress,
    User,
    UserCredentials,
    Weight,
)
from security import decrypt_data_for_user

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init_api(email: str, password: str, user_id: int):
    """Initialize Garmin API with proper authentication using provided credentials."""
    # User-specific token storage to prevent cross-user data bleed
    # Use the mounted volume path instead of home directory
    tokenstore_dir = f"/app/.garminconnect/user_{user_id}"
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
    """Extract sleep data for a specific date and user using Pydantic validation."""
    try:
        raw_sleep_data = api.get_sleep_data(date_str)
        logger.info(f"Sleep API response for {date_str}: {raw_sleep_data}")
        if not raw_sleep_data:
            logger.info(f"No sleep data found for {date_str}")
            return None

        # Extract the actual sleep data from the response
        sleep_dto = raw_sleep_data.get("dailySleepDTO", raw_sleep_data)
        logger.info(
            f"Sleep DTO keys for {date_str}: {list(sleep_dto.keys()) if isinstance(sleep_dto, dict) else type(sleep_dto)}"
        )

        # Use Pydantic for robust parsing
        parsed_sleep = GarminSleepData.from_garmin_response(sleep_dto)
        if not parsed_sleep:
            return None

        # Convert to database model
        return Sleep(
            user_id=user_id,
            date=target_date,
            deep_minutes=(parsed_sleep.deep_sleep_duration or 0) / 60,
            light_minutes=(parsed_sleep.light_sleep_duration or 0) / 60,
            rem_minutes=(parsed_sleep.rem_sleep_duration or 0) / 60,
            awake_minutes=(parsed_sleep.awake_duration or 0) / 60,
            total_sleep_minutes=(parsed_sleep.total_sleep_time or 0) / 60,
            sleep_score=parsed_sleep.sleep_score,
            # New enhanced fields
            body_battery_change=parsed_sleep.body_battery_change,
            skin_temp_celsius=parsed_sleep.skin_temp_celsius,
            awake_count=parsed_sleep.awake_count,
            sleep_quality_score=parsed_sleep.sleep_quality_score,
            sleep_recovery_score=parsed_sleep.sleep_recovery_score,
            spo2_avg=parsed_sleep.spo2_avg,
            spo2_min=parsed_sleep.spo2_min,
            respiratory_rate=parsed_sleep.respiratory_rate,
        )

    except Exception as e:
        logger.warning(f"Failed to extract sleep data for {date_str}: {e}")
        return None


def extract_hrv_data(
    api: Garmin, date_str: str, target_date: datetime.date, user_id: int
) -> HRV | None:
    """Extract HRV data for a specific date and user using Pydantic validation."""
    try:
        raw_hrv_data = api.get_hrv_data(date_str)
        logger.info(f"HRV API response for {date_str}: {raw_hrv_data}")
        if not raw_hrv_data:
            logger.info(f"No HRV data found for {date_str}")
            return None

        # Handle different response formats
        hrv_source = raw_hrv_data
        if "hrvStatusSummary" in raw_hrv_data:
            hrv_source = raw_hrv_data["hrvStatusSummary"]
            logger.info(f"Using hrvStatusSummary for {date_str}")
        elif isinstance(raw_hrv_data, list) and raw_hrv_data:
            hrv_source = raw_hrv_data[0]
            logger.info(f"Using list[0] for HRV {date_str}")

        logger.info(
            f"HRV source keys for {date_str}: {list(hrv_source.keys()) if isinstance(hrv_source, dict) else type(hrv_source)}"
        )

        # Use Pydantic for robust parsing
        parsed_hrv = GarminHRVData.from_garmin_response(hrv_source)
        if not parsed_hrv:
            logger.warning(f"Could not extract HRV from response for {date_str}")
            return None

        # Convert to database model (use RMSSD as primary HRV metric)
        hrv_value = parsed_hrv.hrv_rmssd or parsed_hrv.hrv_sdrr
        if hrv_value is None:
            return None

        return HRV(
            user_id=user_id,
            date=target_date,
            hrv_avg=hrv_value,
            hrv_status="normal",  # Default status, could be enhanced later
        )

    except Exception as e:
        logger.error(f"Failed to process HRV data for {date_str}: {e}")
        return None


def extract_weight_data(
    api: Garmin, date_str: str, target_date: datetime.date, user_id: int
) -> Weight | None:
    """Extract weight and body composition data for a specific date and user."""
    try:
        # Try primary method first
        weight_data = None

        # Method 1: get_daily_weigh_ins (current approach)
        try:
            weight_data = api.get_daily_weigh_ins(date_str)
            logger.info(f"Method 1 (get_daily_weigh_ins) for {date_str}: {weight_data}")
        except Exception as e:
            logger.warning(f"Method 1 failed for {date_str}: {e}")

        # Method 2: Try get_body_composition if method 1 fails or returns empty
        if not weight_data:
            try:
                weight_data = api.get_body_composition(date_str)
                logger.info(
                    f"Method 2 (get_body_composition) for {date_str}: {weight_data}"
                )
            except Exception as e:
                logger.warning(f"Method 2 failed for {date_str}: {e}")

        # Method 3: Try generic get_stats
        if not weight_data:
            try:
                weight_data = api.get_stats(date_str)
                if weight_data:
                    logger.info(f"Method 3 (get_stats) for {date_str}: {weight_data}")
                    # Extract weight from stats if present
                    weight_data = (
                        {"weight": weight_data.get("weight")}
                        if weight_data.get("weight")
                        else None
                    )
            except Exception as e:
                logger.warning(f"Method 3 failed for {date_str}: {e}")

        if not weight_data:
            logger.info(f"All weight extraction methods failed for {date_str}")
            return None

        # Log the structure to understand what we're getting
        logger.info(
            f"Final weight data keys for {date_str}: {list(weight_data.keys()) if isinstance(weight_data, dict) else type(weight_data)}"
        )

        # Extract weight value from the correct location
        weight_value = None

        # Method A: Check dateWeightList first (most accurate)
        if "dateWeightList" in weight_data and weight_data["dateWeightList"]:
            weight_list = weight_data["dateWeightList"]
            if weight_list and len(weight_list) > 0:
                # Get the first (and usually only) weight entry for this date
                weight_entry = weight_list[0]
                weight_value = weight_entry.get("weight")
                logger.info(
                    f"Found weight in dateWeightList for {date_str}: {weight_value}"
                )

        # Method B: Fall back to totalAverage.weight
        if not weight_value and "totalAverage" in weight_data:
            total_avg = weight_data["totalAverage"]
            if total_avg and isinstance(total_avg, dict):
                weight_value = total_avg.get("weight")
                if weight_value is not None:
                    logger.info(
                        f"Found weight in totalAverage for {date_str}: {weight_value}"
                    )

        # Method C: Direct weight key (legacy support)
        if not weight_value:
            weight_value = weight_data.get("weight")
            if weight_value:
                logger.info(
                    f"Found weight at root level for {date_str}: {weight_value}"
                )

        if not weight_value:
            logger.warning(
                f"No weight value found in data for {date_str}. Available keys: {list(weight_data.keys()) if isinstance(weight_data, dict) else 'Not a dict'}"
            )
            return None

        # Convert from grams to kg if needed
        if weight_value > 500:  # Likely in grams
            weight_value = weight_value / 1000.0

        # Extract other body composition data from the same source as weight
        bmi = None
        body_fat_pct = None
        muscle_mass_kg = None
        bone_mass_kg = None
        water_pct = None

        # Extract from dateWeightList if weight came from there
        if "dateWeightList" in weight_data and weight_data["dateWeightList"]:
            weight_entry = weight_data["dateWeightList"][0]
            bmi = weight_entry.get("bmi")
            body_fat_pct = weight_entry.get("bodyFat")
            muscle_mass_kg = (
                weight_entry.get("muscleMass", 0) / 1000
                if weight_entry.get("muscleMass")
                else None
            )
            bone_mass_kg = (
                weight_entry.get("boneMass", 0) / 1000
                if weight_entry.get("boneMass")
                else None
            )
            water_pct = weight_entry.get("bodyWater")

        # Fall back to totalAverage if dateWeightList was empty
        elif "totalAverage" in weight_data and weight_data["totalAverage"]:
            total_avg = weight_data["totalAverage"]
            bmi = total_avg.get("bmi")
            body_fat_pct = total_avg.get("bodyFat")
            muscle_mass_kg = (
                total_avg.get("muscleMass", 0) / 1000
                if total_avg.get("muscleMass")
                else None
            )
            bone_mass_kg = (
                total_avg.get("boneMass", 0) / 1000
                if total_avg.get("boneMass")
                else None
            )
            water_pct = total_avg.get("bodyWater")

        # Legacy fallback
        else:
            bmi = weight_data.get("bmi")
            body_fat_pct = weight_data.get("bodyFat")
            muscle_mass_kg = (
                weight_data.get("muscleMass", 0) / 1000
                if weight_data.get("muscleMass")
                else None
            )
            bone_mass_kg = (
                weight_data.get("boneMass", 0) / 1000
                if weight_data.get("boneMass")
                else None
            )
            water_pct = weight_data.get("bodyWater")

        return Weight(
            user_id=user_id,
            date=target_date,
            weight_kg=weight_value,
            bmi=bmi,
            body_fat_pct=body_fat_pct,
            muscle_mass_kg=muscle_mass_kg,
            bone_mass_kg=bone_mass_kg,
            water_pct=water_pct,
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
        logger.info(f"Heart Rate API response for {date_str}: {hr_data}")
        if not hr_data:
            logger.info(f"No heart rate data found for {date_str}")
            return None

        logger.info(
            f"Heart Rate data keys for {date_str}: {list(hr_data.keys()) if isinstance(hr_data, dict) else type(hr_data)}"
        )

        # Extract values from heart rate API
        resting_hr = hr_data.get("restingHeartRate")
        max_hr = hr_data.get("maxHeartRate")
        avg_hr = hr_data.get("averageHeartRate")

        # If resting HR is not in the heart rate data, try to get it from sleep data
        if not resting_hr:
            try:
                sleep_data = api.get_sleep_data(date_str)
                if sleep_data:
                    # Check main response
                    resting_hr = sleep_data.get("restingHeartRate")
                    # Also check in dailySleepDTO
                    if not resting_hr and "dailySleepDTO" in sleep_data:
                        resting_hr = sleep_data["dailySleepDTO"].get("restingHeartRate")
                    if resting_hr:
                        logger.info(
                            f"Found resting HR in sleep data for {date_str}: {resting_hr}"
                        )
            except Exception as e:
                logger.debug(f"Could not get resting HR from sleep data: {e}")

        return HeartRate(
            user_id=user_id,
            date=target_date,
            resting_hr=resting_hr,
            max_hr=max_hr,
            avg_hr=avg_hr,
        )

    except Exception as e:
        logger.warning(f"Failed to extract heart rate data for {date_str}: {e}")
        return None


def extract_stress_data(
    api: Garmin, date_str: str, target_date: datetime.date, user_id: int
) -> Stress | None:
    """Extract stress data for a specific date and user using Pydantic validation."""
    try:
        raw_stress_data = api.get_stress_data(date_str)
        logger.info(f"Stress API response for {date_str}: {raw_stress_data}")
        if not raw_stress_data:
            logger.info(f"No stress data found for {date_str}")
            return None

        logger.info(
            f"Stress data keys for {date_str}: {list(raw_stress_data.keys()) if isinstance(raw_stress_data, dict) else type(raw_stress_data)}"
        )

        # Use Pydantic for robust parsing
        parsed_stress = GarminStressData.from_garmin_response(raw_stress_data)
        if not parsed_stress:
            logger.warning(f"Could not extract stress from response for {date_str}")
            return None

        # Convert to database model
        return Stress(
            user_id=user_id,
            date=target_date,
            avg_stress=parsed_stress.avg_stress,
            max_stress=parsed_stress.max_stress,
            stress_level="normal",  # Default level, could be enhanced later
            rest_stress=None,  # Not available in current API response
            activity_stress=None,  # Not available in current API response
        )

    except Exception as e:
        logger.error(f"Failed to process stress data for {date_str}: {e}")
        return None


def extract_steps_data_for_range(
    api: Garmin, start_date: datetime.date, end_date: datetime.date, user_id: int
) -> list[Steps]:
    """Extract steps data for a date range using Pydantic validation."""
    try:
        # Format dates for API
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")

        raw_steps_data = api.get_daily_steps(start_str, end_str)
        if not raw_steps_data:
            return []

        steps_records = []
        for daily_data in raw_steps_data:
            # Parse date from response
            date_str = daily_data.get("calendarDate")
            if not date_str:
                continue

            try:
                record_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                continue

            # Use Pydantic for robust parsing
            parsed_steps = GarminStepsData.from_garmin_response(daily_data)
            if not parsed_steps:
                continue

            # Convert to database model
            steps_record = Steps(
                user_id=user_id,
                date=record_date,
                total_steps=parsed_steps.total_steps,
                total_distance=parsed_steps.total_distance,
                step_goal=parsed_steps.step_goal,
            )
            steps_records.append(steps_record)

        return steps_records

    except Exception as e:
        logger.error(
            f"Failed to process steps data for range {start_date} to {end_date}: {e}"
        )
        return []


def sync_garmin_data(user_id: int, days: int = 730) -> dict:
    """
    Sync Garmin data for a specific user for the specified number of days.
    Returns a summary of the sync operation.
    """
    logger.info(
        f"🏥 Starting Garmin data sync for user_id: {user_id}, last {days} days"
    )

    # Calculate and log the date range
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=days)
    logger.info(f"📅 Sync date range: {start_date} to {end_date} ({days} days)")

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
        from typing import cast

        email = cast(str, creds.garmin_email or user.username)
        try:
            password = decrypt_data_for_user(
                cast(str, creds.encrypted_garmin_password), user_id
            )
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

    # Date range (already calculated and logged above)
    # end_date = datetime.date.today()
    # start_date = end_date - datetime.timedelta(days=days)

    # Track sync results
    sync_results = {
        "sleep": {"total": 0, "new": 0, "updated": 0, "errors": 0},
        "hrv": {"total": 0, "new": 0, "updated": 0, "errors": 0},
        "weight": {"total": 0, "new": 0, "updated": 0, "errors": 0},
        "heart_rate": {"total": 0, "new": 0, "updated": 0, "errors": 0},
        "stress": {"total": 0, "new": 0, "updated": 0, "errors": 0},
        "steps": {"total": 0, "new": 0, "updated": 0, "errors": 0},
    }

    with get_db_session_context() as db:
        # Process steps data first (uses range API)
        try:
            steps_records = extract_steps_data_for_range(
                api, start_date, end_date, user_id
            )
            for steps_data in steps_records:
                # Check if record already exists
                existing = db.scalars(
                    select(Steps).filter(
                        Steps.user_id == user_id, Steps.date == steps_data.date
                    )
                ).first()

                if existing:
                    # Check if data has changed before updating
                    has_changes = False
                    for attr in ["total_steps", "total_distance", "step_goal"]:
                        if (
                            hasattr(steps_data, attr)
                            and getattr(steps_data, attr) is not None
                            and getattr(existing, attr) != getattr(steps_data, attr)
                        ):
                            setattr(existing, attr, getattr(steps_data, attr))
                            has_changes = True

                    if has_changes:
                        sync_results["steps"]["updated"] += 1
                    else:
                        sync_results["steps"]["unchanged"] = (
                            sync_results["steps"].get("unchanged", 0) + 1
                        )
                else:
                    db.add(steps_data)
                    sync_results["steps"]["new"] += 1
                sync_results["steps"]["total"] += 1

        except Exception as e:
            logger.error(f"Error processing steps data: {e}")
            sync_results["steps"]["errors"] += 1

        current_date = start_date
        total_days = (end_date - start_date).days + 1
        processed_days = 0

        while current_date <= end_date:
            date_str = current_date.strftime("%Y-%m-%d")
            processed_days += 1
            if (
                processed_days % 50 == 0
                or processed_days == 1
                or processed_days == total_days
            ):
                logger.info(
                    f"📅 Processing {date_str} ({processed_days}/{total_days})..."
                )
            elif processed_days % 10 == 0:
                logger.debug(
                    f"📅 Processing {date_str} ({processed_days}/{total_days})..."
                )

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
