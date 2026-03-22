import datetime
import time
from collections.abc import Callable
from typing import Any

from dotenv import load_dotenv
from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)
from requests.exceptions import RequestException
from tenacity import (
    retry,
    retry_if_exception_type,
    retry_if_not_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from date_utils import utcnow
from enums import DataSource
from errors import CredentialsDecryptionError, CredentialsNotFoundError
from garmin_schemas import (
    GarminActivityData,
    GarminEnergyData,
    GarminHeartRateData,
    GarminHRVData,
    GarminRacePredictionData,
    GarminSleepData,
    GarminStepsData,
    GarminStressData,
    GarminTrainingStatusData,
    GarminWeightData,
)
from logging_config import get_logger
from models import (
    HRV,
    Energy,
    GarminActivity,
    GarminRacePrediction,
    GarminTrainingStatus,
    HeartRate,
    Sleep,
    Steps,
    Stress,
    Weight,
)
from sync_manager import (
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
    except (
        GarminConnectConnectionError,
        GarminConnectTooManyRequestsError,
        RequestException,
        OSError,
    ) as e:
        logger.error(
            "garmin_init_failed",
            user_id=user_id,
            error_type=type(e).__name__,
            error=str(e),
        )
        raise


GARMIN_MAX_HISTORY_DAYS = 1825  # ~5 years for health data
GARMIN_API_RATE_LIMIT_DELAY = 1.0
GARMIN_MAX_RETRIES = 3
GARMIN_CONSECUTIVE_RATE_LIMIT_ABORT = 2


def _save_refreshed_tokens(api: Garmin, user_id: int) -> None:
    from pathlib import Path

    try:
        tokenstore = Path(f"/app/.garminconnect/user_{user_id}")
        tokenstore.mkdir(parents=True, exist_ok=True)
        api.garth.dump(str(tokenstore))
        logger.info("garmin_tokens_refreshed_saved", user_id=user_id)
    except Exception:
        logger.warning("garmin_tokens_save_failed", user_id=user_id, exc_info=True)


def sync_garmin_data_for_user(
    user_id: int, days: int = 90, full_sync: bool = False
) -> dict:
    try:
        creds = get_provider_credentials(user_id, DataSource.GARMIN)
    except (CredentialsNotFoundError, CredentialsDecryptionError) as e:
        logger.error("garmin_credentials_error", user_id=user_id, error=str(e))
        return {"error": str(e), "user_id": user_id}

    if not creds.garmin_email or not creds.garmin_password:
        return {"error": "Garmin credentials not configured", "user_id": user_id}

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
                "unique_fields": ["date", "source"],
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
                "data_type": "energy",
                "api_method": "get_energy_data",
                "parser_class": GarminEnergyData,
                "model_class": Energy,
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
            {
                "data_type": "activities",
                "api_method": "get_activities_data",
                "parser_class": GarminActivityData,
                "model_class": GarminActivity,
                "unique_fields": ["activity_id"],
                "source": "garmin",
                "api_args": {"date_range": dr},
            },
            {
                "data_type": "race_predictions",
                "api_method": "get_race_predictions_data",
                "parser_class": GarminRacePredictionData,
                "model_class": GarminRacePrediction,
                "unique_fields": ["date"],
                "source": "garmin",
                "api_args": {},
            },
        ]

        sync_start = date_range.start_date or datetime.date(2000, 1, 1)
        enhanced_api = GarminAPIWrapper(api, sync_start, date_range.end_date)
        results = batch_sync_data(sync_configs, user_id, enhanced_api)

        _save_refreshed_tokens(api, user_id)

        summary = {
            "user_id": user_id,
            "sync_date": utcnow().isoformat(),
            "sync_type": date_range.sync_type,
            "date_range": {
                "start": (
                    date_range.start_date.isoformat()
                    if date_range.start_date
                    else "all"
                ),
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

    except Exception as e:  # catch-all for sync resilience
        logger.error("garmin_sync_failed", user_id=user_id, error=str(e))
        return {"error": str(e), "user_id": user_id}


class GarminAPIWrapper:
    """Wrapper to adapt Garmin API for batch sync operations."""

    def __init__(self, api: Garmin, start_date: datetime.date, end_date: datetime.date):
        self.api = api
        self.start_date = start_date
        self.end_date = end_date
        self._summary_cache: dict[str, dict | None] = {}
        self._rate_limited = False

    def _get_cached_summary(self, date_str: str) -> dict | None:
        if date_str not in self._summary_cache:
            try:
                result = self.api.get_user_summary(date_str)
                self._summary_cache[date_str] = (
                    result if result and isinstance(result, dict) else None
                )
            except (
                GarminConnectConnectionError,
                GarminConnectTooManyRequestsError,
                GarminConnectAuthenticationError,
                RequestException,
                KeyError,
                ValueError,
                TypeError,
            ) as e:
                logger.warning(
                    "garmin_user_summary_error",
                    date=date_str,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                self._summary_cache[date_str] = None
        return self._summary_cache[date_str]

    def _append_fetched_data(
        self, results: list[dict], data: dict | list[dict] | None
    ) -> None:
        if not data:
            return
        if isinstance(data, list):
            for x in data:
                if isinstance(x, dict):
                    results.append(dict(x))
        elif isinstance(data, dict):
            results.append(dict(data))

    def _fetch_daily(
        self,
        date_range: tuple,
        data_type: str,
        fetcher: Callable[[str, datetime.date], dict | list[dict] | None],
    ) -> list[dict]:
        if self._rate_limited:
            logger.info("garmin_skipping_rate_limited", data_type=data_type)
            return []

        results: list[dict] = []
        start_date, end_date = date_range
        consecutive_rate_limits = 0

        @retry(
            stop=stop_after_attempt(GARMIN_MAX_RETRIES),
            wait=wait_exponential(multiplier=1, min=2, max=30),
            retry=(
                retry_if_exception_type(Exception)
                & retry_if_not_exception_type(GarminConnectTooManyRequestsError)
            ),
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
                self._append_fetched_data(results, data)
                consecutive_rate_limits = 0
            except GarminConnectTooManyRequestsError:
                consecutive_rate_limits += 1
                logger.warning(
                    "garmin_rate_limit_hit",
                    data_type=data_type,
                    date=str(current_date),
                    consecutive=consecutive_rate_limits,
                )
                if consecutive_rate_limits >= GARMIN_CONSECUTIVE_RATE_LIMIT_ABORT:
                    self._rate_limited = True
                    logger.error(
                        "garmin_rate_limit_abort",
                        data_type=data_type,
                        date=str(current_date),
                        consecutive=consecutive_rate_limits,
                        fetched_so_far=len(results),
                    )
                    raise
            except (
                GarminConnectConnectionError,
                GarminConnectAuthenticationError,
                RequestException,
                KeyError,
                ValueError,
                TypeError,
            ) as e:
                consecutive_rate_limits = 0
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

    def _steps_from_summary(
        self, summary: dict, current_date: datetime.date
    ) -> dict | None:
        result = {
            "date": current_date,
            "totalSteps": self._safe_int(summary.get("totalSteps")),
            "totalDistance": self._safe_float(summary.get("totalDistanceMeters")),
            "stepGoal": self._safe_int(summary.get("dailyStepGoal")),
            "activeMinutes": (
                self._safe_int(summary.get("vigorousIntensityMinutes", 0) or 0) or 0
            )
            + (self._safe_int(summary.get("moderateIntensityMinutes", 0) or 0) or 0),
            "floorsClimbed": self._safe_int(summary.get("floorsAscended")),
        }
        return result if result["totalSteps"] is not None else None

    def _steps_from_hourly_buckets(
        self, date_str: str, current_date: datetime.date
    ) -> dict | None:
        steps_data = self.api.get_steps_data(date_str)
        if not steps_data or not isinstance(steps_data, list):
            return None
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

    def get_steps_data(self, date_range: tuple) -> list[dict]:
        def fetch(date_str: str, current_date: datetime.date) -> dict | None:
            summary = self._get_cached_summary(date_str)
            if summary:
                result = self._steps_from_summary(summary, current_date)
                if result is not None:
                    return result
            return self._steps_from_hourly_buckets(date_str, current_date)

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

    def _weight_entries_from_date_list(
        self, date_weight_list: list, current_date: datetime.date
    ) -> list[dict]:
        results: list[dict] = []
        for item in date_weight_list:
            if isinstance(item, dict) and item.get("weight"):
                entry = dict(item)
                entry["date"] = current_date
                results.append(entry)
        return results

    def _weight_entry_from_total_average(
        self, weight_response: dict, current_date: datetime.date
    ) -> list[dict]:
        total_avg = weight_response.get("totalAverage", {})
        if (
            total_avg
            and isinstance(total_avg, dict)
            and total_avg.get("weight") is not None
        ):
            return [
                {
                    "date": current_date,
                    "weight": total_avg.get("weight"),
                    "bmi": total_avg.get("bmi"),
                    "bodyFat": total_avg.get("bodyFat"),
                    "bodyWater": total_avg.get("bodyWater"),
                    "boneMass": total_avg.get("boneMass"),
                    "muscleMass": total_avg.get("muscleMass"),
                }
            ]
        return []

    def get_weight_data(self, date_range: tuple) -> list[dict]:
        def fetch(date_str: str, current_date: datetime.date) -> list[dict] | None:
            weight_response = self.api.get_weigh_ins(date_str, date_str)
            if not weight_response or not isinstance(weight_response, dict):
                return None

            date_weight_list = weight_response.get("dateWeightList", [])
            if date_weight_list and isinstance(date_weight_list, list):
                results = self._weight_entries_from_date_list(
                    date_weight_list, current_date
                )
            elif not date_weight_list:
                results = self._weight_entry_from_total_average(
                    weight_response, current_date
                )
            else:
                results = []
            return results if results else None

        return self._fetch_daily(date_range, "weight", fetch)

    def get_heart_rates_data(self, date_range: tuple) -> list[dict]:
        def fetch(date_str: str, current_date: datetime.date) -> dict | None:
            hr_data = self.api.get_heart_rates(date_str)
            if not hr_data:
                return None

            result = dict(hr_data)
            result["date"] = current_date

            try:
                time.sleep(GARMIN_API_RATE_LIMIT_DELAY)
                spo2_data = self.api.get_spo2_data(date_str)
                if spo2_data and isinstance(spo2_data, dict):
                    result["averageSpO2"] = spo2_data.get("averageSpO2")
                    result["lowestSpO2"] = spo2_data.get("lowestSpO2")
            except (
                GarminConnectConnectionError,
                GarminConnectTooManyRequestsError,
                RequestException,
                KeyError,
                ValueError,
                TypeError,
            ) as e:
                logger.debug("garmin_spo2_error", date=date_str, error=str(e))

            try:
                time.sleep(GARMIN_API_RATE_LIMIT_DELAY)
                resp_data = self.api.get_respiration_data(date_str)
                if resp_data and isinstance(resp_data, dict):
                    result["avgWakingRespirationValue"] = resp_data.get(
                        "avgWakingRespirationValue"
                    )
                    result["lowestRespirationValue"] = resp_data.get(
                        "lowestRespirationValue"
                    )
                    result["highestRespirationValue"] = resp_data.get(
                        "highestRespirationValue"
                    )
            except (
                GarminConnectConnectionError,
                GarminConnectTooManyRequestsError,
                RequestException,
                KeyError,
                ValueError,
                TypeError,
            ) as e:
                logger.debug("garmin_respiration_error", date=date_str, error=str(e))

            return result

        return self._fetch_daily(date_range, "heart_rate", fetch)

    def _safe_int(self, value: Any) -> int | None:
        """Safely convert value to int."""
        if value is None:
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    def get_energy_data(self, date_range: tuple) -> list[dict]:
        def fetch(date_str: str, current_date: datetime.date) -> dict | None:
            summary = self._get_cached_summary(date_str)
            if not summary:
                return None

            active = self._safe_float(summary.get("activeKilocalories"))
            total = self._safe_float(summary.get("totalKilocalories"))
            bmr = self._safe_float(summary.get("bmrKilocalories"))

            if active is None and total is None:
                return None

            if bmr is not None:
                basal = bmr
            elif total is not None and active is not None:
                basal = total - active
            else:
                basal = None

            return {
                "date": current_date,
                "activeKilocalories": active,
                "bmrKilocalories": basal,
            }

        return self._fetch_daily(date_range, "energy", fetch)

    def _fetch_training_status_fields(
        self, date_str: str, combined_data: dict[str, Any]
    ) -> None:
        try:
            training_status = self.api.get_training_status(date_str)
            logger.debug(
                "garmin_training_status_raw",
                date=date_str,
                response_type=type(training_status).__name__,
                is_dict=isinstance(training_status, dict),
                is_empty=not training_status,
            )
            if not training_status or not isinstance(training_status, dict):
                return
            acute_load_dto = self._extract_acute_training_load_dto(training_status)
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
        except (
            GarminConnectConnectionError,
            GarminConnectTooManyRequestsError,
            RequestException,
            KeyError,
            ValueError,
            TypeError,
        ) as e:
            logger.warning(
                "garmin_training_status_error",
                date=date_str,
                error=str(e),
                error_type=type(e).__name__,
            )

    def _fetch_max_metrics_fields(
        self, date_str: str, combined_data: dict[str, Any]
    ) -> None:
        try:
            max_metrics = self.api.get_max_metrics(date_str)
            if not max_metrics or not isinstance(max_metrics, dict):
                return
            generic = max_metrics.get("generic")
            if generic and isinstance(generic, dict):
                combined_data["vo2MaxValue"] = self._safe_float(
                    generic.get("vo2MaxValue")
                )
                combined_data["vo2MaxPreciseValue"] = self._safe_float(
                    generic.get("vo2MaxPreciseValue")
                )
            logger.debug(
                "garmin_max_metrics_response",
                date=date_str,
                vo2_max=combined_data.get("vo2MaxValue"),
            )
        except (
            GarminConnectConnectionError,
            GarminConnectTooManyRequestsError,
            RequestException,
            KeyError,
            ValueError,
            TypeError,
        ) as e:
            logger.warning(
                "garmin_max_metrics_error",
                date=date_str,
                error=str(e),
                error_type=type(e).__name__,
            )

    def _fetch_fitnessage_fields(
        self, date_str: str, combined_data: dict[str, Any]
    ) -> None:
        try:
            fitnessage = self.api.get_fitnessage_data(date_str)
            if not fitnessage or not isinstance(fitnessage, dict):
                return
            combined_data["fitnessAge"] = self._safe_int(fitnessage.get("fitnessAge"))
            logger.debug(
                "garmin_fitnessage_response",
                date=date_str,
                fitness_age=combined_data.get("fitnessAge"),
            )
        except (
            GarminConnectConnectionError,
            GarminConnectTooManyRequestsError,
            RequestException,
            KeyError,
            ValueError,
            TypeError,
        ) as e:
            logger.warning(
                "garmin_fitnessage_error",
                date=date_str,
                error=str(e),
                error_type=type(e).__name__,
            )

    def _fetch_endurance_score_fields(
        self, date_str: str, combined_data: dict[str, Any]
    ) -> None:
        try:
            endurance = self.api.get_endurance_score(date_str)
            if endurance and isinstance(endurance, dict):
                combined_data["enduranceScore"] = endurance.get(
                    "overallScore"
                ) or endurance.get("enduranceScore")
        except (
            GarminConnectConnectionError,
            GarminConnectTooManyRequestsError,
            RequestException,
            KeyError,
            ValueError,
            TypeError,
        ) as e:
            logger.warning(
                "garmin_endurance_score_error",
                date=date_str,
                error=str(e),
                error_type=type(e).__name__,
            )

    def _fetch_readiness_fields(
        self, date_str: str, combined_data: dict[str, Any]
    ) -> None:
        try:
            readiness: Any = self.api.get_training_readiness(date_str)
            if not readiness:
                return
            if isinstance(readiness, list) and len(readiness) > 0:
                morning_entry = next(
                    (
                        entry
                        for entry in readiness
                        if isinstance(entry, dict)
                        and entry.get("inputContext") == "AFTER_WAKEUP_RESET"
                    ),
                    readiness[0],
                )
                if isinstance(morning_entry, dict):
                    combined_data["trainingReadinessScore"] = morning_entry.get("score")
            elif isinstance(readiness, dict):
                combined_data["trainingReadinessScore"] = readiness.get("score")
        except (
            GarminConnectConnectionError,
            GarminConnectTooManyRequestsError,
            RequestException,
            KeyError,
            ValueError,
            TypeError,
        ) as e:
            logger.warning(
                "garmin_training_readiness_error",
                date=date_str,
                error=str(e),
                error_type=type(e).__name__,
            )

    _TRAINING_MEANINGFUL_KEYS = [
        "vo2MaxValue",
        "fitnessAge",
        "trainingLoad7Days",
        "totalKilocalories",
        "enduranceScore",
        "trainingReadinessScore",
    ]

    def get_training_status_data(self, date_range: tuple) -> list[dict]:
        def fetch(date_str: str, current_date: datetime.date) -> dict | None:
            combined_data: dict[str, Any] = {"date": current_date}

            self._fetch_training_status_fields(date_str, combined_data)
            self._fetch_max_metrics_fields(date_str, combined_data)
            self._fetch_fitnessage_fields(date_str, combined_data)

            summary = self._get_cached_summary(date_str)
            if summary:
                combined_data["totalKilocalories"] = self._safe_float(
                    summary.get("totalKilocalories")
                )
                combined_data["activeKilocalories"] = self._safe_float(
                    summary.get("activeKilocalories")
                )

            self._fetch_endurance_score_fields(date_str, combined_data)
            self._fetch_readiness_fields(date_str, combined_data)

            if any(
                combined_data.get(k) is not None for k in self._TRAINING_MEANINGFUL_KEYS
            ):
                return combined_data
            return None

        return self._fetch_daily(date_range, "training_status", fetch)

    def _fetch_hr_zones_for_activity(self, activity_id: str) -> dict[str, int | None]:
        try:
            hr_zones = self.api.get_activity_hr_in_timezones(activity_id)
            if not hr_zones or not isinstance(hr_zones, list):
                return {}

            zone_map: dict[str, int | None] = {}
            for zone in hr_zones:
                if not isinstance(zone, dict):
                    continue
                zone_number = zone.get("zoneNumber")
                secs = zone.get("secsInZone")
                if zone_number is not None and secs is not None:
                    key = f"hr_zone_{self._zone_number_to_name(zone_number)}_seconds"
                    if key.startswith("hr_zone_") and not key.startswith("hr_zone__"):
                        zone_map[key] = int(secs)
            return zone_map
        except (
            GarminConnectConnectionError,
            GarminConnectTooManyRequestsError,
            RequestException,
            KeyError,
            ValueError,
            TypeError,
        ) as e:
            logger.debug(
                "garmin_hr_zones_error",
                activity_id=activity_id,
                error=str(e),
            )
            return {}

    @staticmethod
    def _zone_number_to_name(zone_number: int) -> str:
        names = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five"}
        return names.get(zone_number, "")

    def _parse_activity_date(self, activity: dict) -> datetime.date | None:
        start_time_str = activity.get("startTimeLocal") or activity.get("startTimeGMT")
        if not start_time_str:
            return None
        try:
            if isinstance(start_time_str, str):
                start_dt = datetime.datetime.fromisoformat(
                    start_time_str.replace("Z", "+00:00")
                )
                return start_dt.date()
            if isinstance(start_time_str, (int, float)):
                start_dt = datetime.datetime.fromtimestamp(
                    start_time_str / 1000, tz=datetime.UTC
                )
                return start_dt.date()
        except (ValueError, OSError):
            return None
        return None

    def _enrich_activity_with_date_and_zones(self, activity: dict) -> dict | None:
        activity_data = dict(activity)
        date = self._parse_activity_date(activity)
        if date is None:
            return None
        activity_data["date"] = date

        activity_id = activity.get("activityId")
        if activity_id:
            time.sleep(GARMIN_API_RATE_LIMIT_DELAY)
            zone_data = self._fetch_hr_zones_for_activity(str(activity_id))
            activity_data.update(zone_data)

        return activity_data

    def get_activities_data(self, date_range: tuple) -> list[dict]:
        start_date, end_date = date_range
        results: list[dict] = []

        try:
            start_str = start_date.strftime("%Y-%m-%d")
            end_str = end_date.strftime("%Y-%m-%d")

            activities = self.api.get_activities_by_date(start_str, end_str)
            if not activities or not isinstance(activities, list):
                return []

            for activity in activities:
                if not isinstance(activity, dict):
                    continue
                enriched = self._enrich_activity_with_date_and_zones(activity)
                if enriched is not None:
                    results.append(enriched)

            logger.info(
                "garmin_activities_fetched",
                start_date=start_str,
                end_date=end_str,
                count=len(results),
            )

        except (
            GarminConnectConnectionError,
            GarminConnectTooManyRequestsError,
            GarminConnectAuthenticationError,
            RequestException,
            KeyError,
            ValueError,
            TypeError,
        ) as e:
            logger.warning(
                "garmin_activities_error",
                error_type=type(e).__name__,
                error=str(e),
            )

        return results

    _RACE_DISTANCE_KEY_MAP = {
        5000: "prediction_5k_seconds",
        10000: "prediction_10k_seconds",
        21097: "prediction_half_marathon_seconds",
        21098: "prediction_half_marathon_seconds",
        42195: "prediction_marathon_seconds",
    }

    _RACE_PREDICTION_MEANINGFUL_KEYS = [
        "prediction_5k_seconds",
        "prediction_10k_seconds",
        "prediction_half_marathon_seconds",
        "prediction_marathon_seconds",
    ]

    def _extract_vo2_from_predictions(
        self, predictions: dict, result: dict[str, Any]
    ) -> None:
        for vo2_key in ("overallVO2Max", "vo2MaxValue", "vo2Max"):
            val = predictions.get(vo2_key)
            if val is not None:
                result["vo2MaxValue"] = self._safe_float(val)
                break

    def _extract_single_race(self, race: dict, result: dict[str, Any]) -> None:
        raw_distance = race.get("distance") or race.get("racePredictionDistance")
        distance = int(raw_distance) if raw_distance is not None else None
        time_secs = race.get("time") or race.get("racePredictionTime")
        if (
            distance is not None
            and distance in self._RACE_DISTANCE_KEY_MAP
            and time_secs is not None
        ):
            result[self._RACE_DISTANCE_KEY_MAP[distance]] = self._safe_int(time_secs)

    def _extract_race_times(self, predictions: dict, result: dict[str, Any]) -> None:
        for list_key in ("raceTimes", "racePredictions"):
            race_list = predictions.get(list_key, [])
            if not isinstance(race_list, list):
                continue
            for race in race_list:
                if isinstance(race, dict):
                    self._extract_single_race(race, result)

    def get_race_predictions_data(self) -> list[dict]:
        try:
            predictions = self.api.get_race_predictions()
            if not predictions or not isinstance(predictions, dict):
                return []

            result: dict[str, Any] = {"date": datetime.date.today()}
            self._extract_vo2_from_predictions(predictions, result)
            self._extract_race_times(predictions, result)

            if any(
                result.get(k) is not None for k in self._RACE_PREDICTION_MEANINGFUL_KEYS
            ):
                logger.info("garmin_race_predictions_fetched", keys=list(result.keys()))
                return [result]

            return []

        except (
            GarminConnectConnectionError,
            GarminConnectTooManyRequestsError,
            GarminConnectAuthenticationError,
            RequestException,
            KeyError,
            ValueError,
            TypeError,
        ) as e:
            logger.warning(
                "garmin_race_predictions_error",
                error_type=type(e).__name__,
                error=str(e),
            )
            return []


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
