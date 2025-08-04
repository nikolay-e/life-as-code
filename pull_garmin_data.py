"""
Garmin Connect Data Extractor - Refactored with Sync Manager
Extracts health data from Garmin Connect and stores it in PostgreSQL database.
"""

import datetime
import logging
import os

from dotenv import load_dotenv
from garminconnect import Garmin, GarminConnectAuthenticationError

from database import get_db_session_context
from garmin_schemas import (
    GarminHRVData,
    GarminSleepData,
    GarminStepsData,
    GarminStressData,
)
from models import HRV, Sleep, Steps, Stress
from security import decrypt_data_for_user
from sync_manager import batch_sync_data, get_sync_statistics

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init_api(email: str, password: str, user_id: int) -> Garmin:
    """Initialize Garmin API with proper authentication using provided credentials."""
    # User-specific token storage to prevent cross-user data bleed
    tokenstore_dir = f"/app/.garminconnect/user_{user_id}"
    tokenstore = os.path.join(tokenstore_dir, "tokens")
    os.makedirs(tokenstore_dir, exist_ok=True)

    try:
        api = Garmin(email, password, tokenstore=tokenstore)
        api.login()
        return api
    except (GarminConnectAuthenticationError, Exception) as e:
        logger.error(f"Failed to authenticate with Garmin: {e}")
        raise


def sync_garmin_data_for_user(user_id: int, days: int = 730) -> dict:
    """
    Main function to sync all Garmin data for a user using the sync manager.

    Args:
        user_id: User ID to sync data for
        days: Number of days back to sync

    Returns:
        dict: Summary of sync results
    """
    from sqlalchemy import select

    from models import UserCredentials

    # Get user credentials
    try:
        with get_db_session_context() as db:
            creds = db.scalars(
                select(UserCredentials).where(UserCredentials.user_id == user_id)
            ).first()

            if not creds or not creds.garmin_email:
                return {"error": "No Garmin credentials found for user"}

            # Decrypt password
            garmin_password = decrypt_data_for_user(
                creds.encrypted_garmin_password, user_id
            )
    except Exception as e:
        return {"error": f"Failed to get user credentials: {str(e)}"}

    try:
        # Initialize Garmin API
        api = init_api(creds.garmin_email, garmin_password, user_id)

        # Calculate date range
        end_date = datetime.date.today()
        start_date = end_date - datetime.timedelta(days=days)

        # Define sync configurations for all Garmin data types
        sync_configs = [
            {
                "data_type": "sleep",
                "api_method": "get_sleep_data",
                "parser_class": GarminSleepData,
                "model_class": Sleep,
                "unique_fields": ["date"],
                "source": "garmin",
                "api_args": {"date_range": (start_date, end_date)},
            },
            {
                "data_type": "hrv",
                "api_method": "get_hrv_data",
                "parser_class": GarminHRVData,
                "model_class": HRV,
                "unique_fields": ["date"],
                "source": "garmin",
                "api_args": {"date_range": (start_date, end_date)},
            },
            {
                "data_type": "stress",
                "api_method": "get_stress_data",
                "parser_class": GarminStressData,
                "model_class": Stress,
                "unique_fields": ["date"],
                "source": "garmin",
                "api_args": {"date_range": (start_date, end_date)},
            },
            {
                "data_type": "steps",
                "api_method": "get_steps_data",
                "parser_class": GarminStepsData,
                "model_class": Steps,
                "unique_fields": ["date"],
                "source": "garmin",
                "api_args": {"date_range": (start_date, end_date)},
            },
        ]

        # Create enhanced API wrapper for batch operations
        enhanced_api = GarminAPIWrapper(api, start_date, end_date)

        # Run batch sync
        results = batch_sync_data(sync_configs, user_id, enhanced_api)

        # Compile summary
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

        logger.info(f"Garmin sync completed for user {user_id}: {summary}")
        return summary

    except Exception as e:
        error_msg = f"Failed to sync Garmin data for user {user_id}: {str(e)}"
        logger.error(error_msg)
        return {"error": error_msg, "user_id": user_id}


class GarminAPIWrapper:
    """Wrapper to adapt Garmin API for batch sync operations."""

    def __init__(self, api: Garmin, start_date: datetime.date, end_date: datetime.date):
        self.api = api
        self.start_date = start_date
        self.end_date = end_date

    def get_sleep_data(self, date_range: tuple) -> list[dict]:
        """Get sleep data for date range."""
        results = []
        start_date, end_date = date_range

        current_date = start_date
        while current_date <= end_date:
            try:
                date_str = current_date.strftime("%Y-%m-%d")
                sleep_data = self.api.get_sleep_data(date_str)

                if sleep_data:
                    # Extract the actual sleep data and add date
                    sleep_dto = sleep_data.get("dailySleepDTO", sleep_data)
                    sleep_dto["date"] = current_date
                    results.append(sleep_dto)

            except Exception as e:
                logger.warning(f"Failed to get sleep data for {current_date}: {e}")

            current_date += datetime.timedelta(days=1)

        return results

    def get_hrv_data(self, date_range: tuple) -> list[dict]:
        """Get HRV data for date range."""
        results = []
        start_date, end_date = date_range

        current_date = start_date
        while current_date <= end_date:
            try:
                date_str = current_date.strftime("%Y-%m-%d")
                hrv_data = self.api.get_hrv_data(date_str)

                if hrv_data:
                    hrv_data["date"] = current_date
                    results.append(hrv_data)

            except Exception as e:
                logger.warning(f"Failed to get HRV data for {current_date}: {e}")

            current_date += datetime.timedelta(days=1)

        return results

    def get_stress_data(self, date_range: tuple) -> list[dict]:
        """Get stress data for date range."""
        results = []
        start_date, end_date = date_range

        current_date = start_date
        while current_date <= end_date:
            try:
                date_str = current_date.strftime("%Y-%m-%d")
                stress_data = self.api.get_stress_data(date_str)

                if stress_data:
                    stress_data["date"] = current_date
                    results.append(stress_data)

            except Exception as e:
                logger.warning(f"Failed to get stress data for {current_date}: {e}")

            current_date += datetime.timedelta(days=1)

        return results

    def get_steps_data(self, date_range: tuple) -> list[dict]:
        """Get steps data for date range."""
        results = []
        start_date, end_date = date_range

        current_date = start_date
        while current_date <= end_date:
            try:
                date_str = current_date.strftime("%Y-%m-%d")
                steps_data = self.api.get_steps_data(date_str)

                if steps_data:
                    steps_data["date"] = current_date
                    results.append(steps_data)

            except Exception as e:
                logger.warning(f"Failed to get steps data for {current_date}: {e}")

            current_date += datetime.timedelta(days=1)

        return results


def get_garmin_sync_status(user_id: int) -> dict:
    """Get sync status for Garmin data."""
    return get_sync_statistics(user_id, source="garmin")


if __name__ == "__main__":
    # Example usage
    import sys

    if len(sys.argv) > 1:
        user_id = int(sys.argv[1])
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 730

        result = sync_garmin_data_for_user(user_id, days)
        print(f"Sync result: {result}")
    else:
        print("Usage: python pull_garmin_data.py <user_id> [days]")
