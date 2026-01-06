import datetime
import time
from collections.abc import Callable
from typing import Any

from dotenv import load_dotenv
from garminconnect import Garmin, GarminConnectAuthenticationError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from enums import DataSource
from garmin_schemas import (
    GarminHeartRateData,
    GarminHRVData,
    GarminSleepData,
    GarminStepsData,
    GarminStressData,
    GarminTrainingStatusData,
    GarminWeightData,
)
from logging_config import get_logger
from models import HRV, GarminTrainingStatus, HeartRate, Sleep, Steps, Stress, Weight
from sync_manager import (
    ProviderCredentials,
    batch_sync_data,
    get_provider_credentials,
    get_sync_date_range,
)

load_dotenv()

logger = get_logger(__name__)


def init_api(email: str, password: str, user_id: int) -> Garmin:
    """Initialize Garmin API with proper authentication using provided credentials."""
    from pathlib import Path

    # User-specific token storage for persistent sessions
    tokenstore = Path(f"/app/.garminconnect/user_{user_id}")
    tokenstore.mkdir(parents=True, exist_ok=True)

    try:
        # Try to use existing tokens first
        if (tokenstore / "oauth1_token.json").exists():
            logger.info("garmin_loading_tokens", user_id=user_id)
            api = Garmin()
            api.login(str(tokenstore))
            return api

        # First-time login with credentials
        logger.info("garmin_first_login", user_id=user_id)
        api = Garmin(email, password)
        api.login()

        # Save tokens for future use
        api.garth.dump(str(tokenstore))
        logger.info("garmin_tokens_saved", user_id=user_id)
        return api

    except GarminConnectAuthenticationError as e:
        logger.error(
            "garmin_auth_failed",
            user_id=user_id,
            error_type="authentication",
            error=str(e),
        )
        raise
    except Exception as e:
        logger.error(
            "garmin_init_failed",
            user_id=user_id,
            error_type=type(e).__name__,
            error=str(e),
        )
        raise


GARMIN_MAX_HISTORY_DAYS = 1825  # ~5 years for health data
GARMIN_API_RATE_LIMIT_DELAY = 0.5  # seconds between API calls to avoid rate limiting
GARMIN_MAX_RETRIES = 3


def sync_garmin_data_for_user(
    user_id: int, days: int = 90, full_sync: bool = False
) -> dict:
    creds = get_provider_credentials(user_id, DataSource.GARMIN)
    if isinstance(creds, dict):
        return creds
    assert isinstance(creds, ProviderCredentials)

    try:
        api = init_api(creds.garmin_email, creds.garmin_password, user_id)
        date_range = get_sync_date_range(days, full_sync, GARMIN_MAX_HISTORY_DAYS)

        logger.info(
            "garmin_sync_started",
            user_id=user_id,
            sync_type=date_range.sync_type,
            start_date=date_range.start_date,
            end_date=date_range.end_date,
            full_sync=full_sync,
        )

        dr = (date_range.start_date, date_range.end_date)
        sync_configs = [
            {
                "data_type": "sleep",
                "api_method": "get_sleep_data",
                "parser_class": GarminSleepData,
                "model_class": Sleep,
                "unique_fields": ["date", "source"],
                "source": "garmin",
                "api_args": {"date_range": dr},
            },
            {
                "data_type": "hrv",
                "api_method": "get_hrv_data",
                "parser_class": GarminHRVData,
                "model_class": HRV,
                "unique_fields": ["date", "source"],
                "source": "garmin",
                "api_args": {"date_range": dr},
            },
            {
                "data_type": "stress",
                "api_method": "get_stress_data",
                "parser_class": GarminStressData,
                "model_class": Stress,
                "unique_fields": ["date"],
                "source": "garmin",
                "api_args": {"date_range": dr},
            },
            {
                "data_type": "steps",
                "api_method": "get_steps_data",
                "parser_class": GarminStepsData,
                "model_class": Steps,
                "unique_fields": ["date", "source"],
                "source": "garmin",
                "api_args": {"date_range": dr},
            },
            {
                "data_type": "weight",
                "api_method": "get_weight_data",
                "parser_class": GarminWeightData,
                "model_class": Weight,
                "unique_fields": ["date", "source"],
                "source": "garmin",
                "api_args": {"date_range": dr},
            },
            {
                "data_type": "heart_rate",
                "api_method": "get_heart_rates_data",
                "parser_class": GarminHeartRateData,
                "model_class": HeartRate,
                "unique_fields": ["date", "source"],
                "source": "garmin",
                "api_args": {"date_range": dr},
            },
            {
                "data_type": "training_status",
                "api_method": "get_training_status_data",
                "parser_class": GarminTrainingStatusData,
                "model_class": GarminTrainingStatus,
                "unique_fields": ["date"],
                "source": "garmin",
                "api_args": {"date_range": dr},
            },
        ]

        enhanced_api = GarminAPIWrapper(api, date_range.start_date, date_range.end_date)
        results = batch_sync_data(sync_configs, user_id, enhanced_api)

        summary = {
            "user_id": user_id,
            "sync_date": datetime.datetime.utcnow().isoformat(),
            "sync_type": date_range.sync_type,
            "date_range": {
                "start": date_range.start_date.isoformat(),
                "end": date_range.end_date.isoformat(),
            },
            "results": [r.get_summary() for r in results],
            "total_records_processed": sum(r.records_processed for r in results),
            "total_records_created": sum(r.records_created for r in results),
            "total_records_updated": sum(r.records_updated for r in results),
            "total_errors": sum(len(r.errors) for r in results),
            "success": all(r.success for r in results),
        }

        logger.info(
            "garmin_sync_completed",
            user_id=user_id,
            records_processed=summary["total_records_processed"],
            records_created=summary["total_records_created"],
            success=summary["success"],
        )
        return summary

    except Exception as e:
        logger.error("garmin_sync_failed", user_id=user_id, error=str(e))
        return {"error": str(e), "user_id": user_id}


class GarminAPIWrapper:
    """Wrapper to adapt Garmin API for batch sync operations."""

    def __init__(self, api: Garmin, start_date: datetime.date, end_date: datetime.date):
        self.api = api
        self.start_date = start_date
        self.end_date = end_date

    def _fetch_daily(
        self,
        date_range: tuple,
        data_type: str,
        fetcher: Callable[[str, datetime.date], dict | list[dict] | None],
    ) -> list[dict]:
        """Generic daily data fetcher with retry, rate limiting, and error handling."""
        results: list[dict] = []
        start_date, end_date = date_range

        @retry(
            stop=stop_after_attempt(GARMIN_MAX_RETRIES),
            wait=wait_exponential(multiplier=1, min=2, max=30),
            retry=retry_if_exception_type(Exception),
            reraise=True,
        )
        def _fetch_with_retry(
            date_str: str, current_date: datetime.date
        ) -> dict | list[dict] | None:
            return fetcher(date_str, current_date)

        current_date = start_date
        while current_date <= end_date:
            try:
                date_str = current_date.strftime("%Y-%m-%d")
                data = _fetch_with_retry(date_str, current_date)
                if data:
                    if isinstance(data, list):
                        for x in data:
                            if isinstance(x, dict):
                                results.append(dict(x))
                    elif isinstance(data, dict):
                        results.append(dict(data))
            except Exception as e:
                logger.warning(
                    "garmin_api_error",
                    data_type=data_type,
                    date=str(current_date),
                    error_type=type(e).__name__,
                    error=str(e),
                )

            current_date += datetime.timedelta(days=1)
            time.sleep(GARMIN_API_RATE_LIMIT_DELAY)

        return results

    def get_sleep_data(self, date_range: tuple) -> list[dict]:
        """Get sleep data for date range."""

        def fetch(date_str: str, current_date: datetime.date) -> dict | None:
            sleep_data = self.api.get_sleep_data(date_str)
            if sleep_data:
                sleep_dto = dict(sleep_data.get("dailySleepDTO", sleep_data))
                sleep_dto["date"] = current_date
                return sleep_dto
            return None

        return self._fetch_daily(date_range, "sleep", fetch)

    def get_hrv_data(self, date_range: tuple) -> list[dict]:
        """Get HRV data for date range. Flattens nested hrvSummary structure."""

        def fetch(date_str: str, current_date: datetime.date) -> dict | None:
            hrv_data = self.api.get_hrv_data(date_str)
            if not hrv_data:
                return None

            flattened: dict[str, Any] = {"date": current_date}
            hrv_summary = hrv_data.get("hrvSummary", {})
            if hrv_summary and isinstance(hrv_summary, dict):
                flattened["lastNightAvg"] = hrv_summary.get("lastNightAvg")
                flattened["status"] = hrv_summary.get("status")
                flattened["baselineLowMs"] = hrv_summary.get("baselineLowMs")
                flattened["baselineHighMs"] = hrv_summary.get("baselineHighMs")
                flattened["weeklyAvg"] = hrv_summary.get("weeklyAvg")
                flattened["feedbackPhrase"] = hrv_summary.get("feedbackPhrase")
            else:
                flattened.update(hrv_data)
                flattened["date"] = current_date
            return flattened

        return self._fetch_daily(date_range, "hrv", fetch)

    def get_stress_data(self, date_range: tuple) -> list[dict]:
        """Get stress data for date range."""

        def fetch(date_str: str, current_date: datetime.date) -> dict | None:
            stress_data = self.api.get_stress_data(date_str)
            if stress_data:
                result = dict(stress_data)
                result["date"] = current_date
                return result
            return None

        return self._fetch_daily(date_range, "stress", fetch)

    def get_steps_data(self, date_range: tuple) -> list[dict]:
        """Get steps data for date range. Uses get_user_summary with fallback to hourly buckets."""

        def fetch(date_str: str, current_date: datetime.date) -> dict | None:
            # Try get_user_summary first for comprehensive daily stats
            try:
                summary = self.api.get_user_summary(date_str)
                if summary and isinstance(summary, dict):
                    result = {
                        "date": current_date,
                        "totalSteps": self._safe_int(summary.get("totalSteps")),
                        "totalDistance": self._safe_float(
                            summary.get("totalDistanceMeters")
                        ),
                        "stepGoal": self._safe_int(summary.get("dailyStepGoal")),
                        "activeMinutes": (
                            self._safe_int(
                                summary.get("vigorousIntensityMinutes", 0) or 0
                            )
                            or 0
                        )
                        + (
                            self._safe_int(
                                summary.get("moderateIntensityMinutes", 0) or 0
                            )
                            or 0
                        ),
                        "floorsClimbed": self._safe_int(summary.get("floorsAscended")),
                    }
                    if result["totalSteps"] is not None:
                        return result
            except Exception:
                pass

            # Fallback to get_steps_data and aggregate hourly buckets
            steps_data = self.api.get_steps_data(date_str)
            if steps_data and isinstance(steps_data, list):
                total_steps = sum(
                    self._safe_int(bucket.get("steps")) or 0
                    for bucket in steps_data
                    if isinstance(bucket, dict)
                )
                if total_steps > 0:
                    return {
                        "date": current_date,
                        "totalSteps": total_steps,
                        "totalDistance": None,
                        "stepGoal": None,
                        "activeMinutes": None,
                        "floorsClimbed": None,
                    }
            return None

        return self._fetch_daily(date_range, "steps", fetch)

    def _safe_float(self, value: Any) -> float | None:
        """Safely convert value to float."""
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    def _extract_acute_training_load_dto(
        self, training_status: dict
    ) -> dict[str, Any] | None:
        """Extract acuteTrainingLoadDTO from nested training status response.

        Garmin API returns training load data in a deeply nested structure:
        latestTrainingStatusData -> {device_id} -> acuteTrainingLoadDTO
        """
        latest_data = training_status.get("latestTrainingStatusData")
        if not latest_data or not isinstance(latest_data, dict):
            return None

        for _device_id, device_data in latest_data.items():
            if not isinstance(device_data, dict):
                continue
            acute_dto = device_data.get("acuteTrainingLoadDTO")
            if acute_dto and isinstance(acute_dto, dict):
                return dict(acute_dto)

        return None

    def get_weight_data(self, date_range: tuple) -> list[dict]:
        """Get weight and body composition data. Weight values are in grams."""

        def fetch(date_str: str, current_date: datetime.date) -> list[dict] | None:
            weight_response = self.api.get_weigh_ins(date_str, date_str)
            if not weight_response or not isinstance(weight_response, dict):
                return None

            results: list[dict] = []
            date_weight_list = weight_response.get("dateWeightList", [])
            if date_weight_list and isinstance(date_weight_list, list):
                for item in date_weight_list:
                    if isinstance(item, dict) and item.get("weight"):
                        entry = dict(item)
                        entry["date"] = current_date
                        results.append(entry)
            elif not date_weight_list:
                total_avg = weight_response.get("totalAverage", {})
                if (
                    total_avg
                    and isinstance(total_avg, dict)
                    and total_avg.get("weight") is not None
                ):
                    results.append(
                        {
                            "date": current_date,
                            "weight": total_avg.get("weight"),
                            "bmi": total_avg.get("bmi"),
                            "bodyFat": total_avg.get("bodyFat"),
                            "bodyWater": total_avg.get("bodyWater"),
                            "boneMass": total_avg.get("boneMass"),
                            "muscleMass": total_avg.get("muscleMass"),
                        }
                    )
            return results if results else None

        return self._fetch_daily(date_range, "weight", fetch)

    def get_heart_rates_data(self, date_range: tuple) -> list[dict]:
        """Get heart rate data for date range."""

        def fetch(date_str: str, current_date: datetime.date) -> dict | None:
            hr_data = self.api.get_heart_rates(date_str)
            if hr_data:
                result = dict(hr_data)
                result["date"] = current_date
                return result
            return None

        return self._fetch_daily(date_range, "heart_rate", fetch)

    def _safe_int(self, value: Any) -> int | None:
        """Safely convert value to int."""
        if value is None:
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    def get_training_status_data(self, date_range: tuple) -> list[dict]:
        """Get training status, VO2Max, fitness age, and related metrics from multiple endpoints."""

        def fetch(date_str: str, current_date: datetime.date) -> dict | None:
            combined_data: dict[str, Any] = {"date": current_date}

            # Get training status (includes VO2 max and training load)
            try:
                training_status = self.api.get_training_status(date_str)
                if training_status and isinstance(training_status, dict):
                    acute_load_dto = self._extract_acute_training_load_dto(
                        training_status
                    )
                    logger.info(
                        "garmin_training_status_response",
                        date=date_str,
                        vo2_max=training_status.get("vo2MaxValue"),
                        fitness_age=training_status.get("fitnessAge"),
                        daily_load_acute=(
                            acute_load_dto.get("dailyTrainingLoadAcute")
                            if acute_load_dto
                            else None
                        ),
                        daily_load_chronic=(
                            acute_load_dto.get("dailyTrainingLoadChronic")
                            if acute_load_dto
                            else None
                        ),
                        has_keys=list(training_status.keys())[:15],
                    )
                    combined_data["vo2MaxValue"] = training_status.get("vo2MaxValue")
                    combined_data["vo2MaxPreciseValue"] = training_status.get(
                        "vo2MaxPreciseValue"
                    )
                    combined_data["fitnessAge"] = training_status.get("fitnessAge")
                    combined_data["trainingStatusLabel"] = training_status.get(
                        "trainingStatusLabel"
                    )
                    combined_data["trainingStatusDescription"] = training_status.get(
                        "trainingStatusDescription"
                    )
                    if acute_load_dto:
                        combined_data["acuteTrainingLoad"] = acute_load_dto.get(
                            "dailyTrainingLoadAcute"
                        )
                        combined_data["trainingLoad7Days"] = acute_load_dto.get(
                            "dailyTrainingLoadChronic"
                        )
                    else:
                        combined_data["acuteTrainingLoad"] = training_status.get(
                            "acuteTrainingLoad"
                        )
                        combined_data["trainingLoad7Days"] = training_status.get(
                            "trainingLoad7Days"
                        ) or training_status.get("sevenDaysTrainingLoad")
                    combined_data["primaryTrainingEffect"] = training_status.get(
                        "primaryTrainingEffect"
                    )
                    combined_data["anaerobicTrainingEffect"] = training_status.get(
                        "anaerobicTrainingEffect"
                    )
            except Exception:
                pass

            # Get user summary for calories
            try:
                summary = self.api.get_user_summary(date_str)
                if summary and isinstance(summary, dict):
                    combined_data["totalKilocalories"] = self._safe_float(
                        summary.get("totalKilocalories")
                    )
                    combined_data["activeKilocalories"] = self._safe_float(
                        summary.get("activeKilocalories")
                    )
            except Exception:
                pass

            # Try to get endurance score
            try:
                endurance = self.api.get_endurance_score(date_str)
                if endurance and isinstance(endurance, dict):
                    combined_data["enduranceScore"] = endurance.get(
                        "overallScore"
                    ) or endurance.get("enduranceScore")
            except Exception:
                pass

            # Only return if we have at least some meaningful data
            meaningful_keys = [
                "vo2MaxValue",
                "fitnessAge",
                "trainingLoad7Days",
                "totalKilocalories",
                "enduranceScore",
            ]
            if any(combined_data.get(k) is not None for k in meaningful_keys):
                return combined_data
            return None

        return self._fetch_daily(date_range, "training_status", fetch)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        user_id = int(sys.argv[1])
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 90
        full_sync = "--full" in sys.argv

        result = sync_garmin_data_for_user(user_id, days, full_sync=full_sync)
        print(f"Sync result: {result}")
    else:
        print("Usage: python pull_garmin_data.py <user_id> [days] [--full]")
