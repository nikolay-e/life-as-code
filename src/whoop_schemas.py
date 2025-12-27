import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from logging_config import get_logger

logger = get_logger(__name__)


class WhoopRecoveryParser(BaseModel):
    """Pydantic model for parsing Whoop Recovery data."""

    recovery_score: int | None = Field(None, description="Recovery score (0-100)")
    resting_heart_rate: int | None = Field(
        None, description="Resting heart rate in bpm"
    )
    hrv_rmssd: float | None = Field(None, description="HRV RMSSD in milliseconds")
    spo2_percentage: float | None = Field(None, description="SpO2 percentage")
    skin_temp_celsius: float | None = Field(
        None, description="Skin temperature in Celsius"
    )
    user_calibrating: int = 0

    @classmethod
    def from_whoop_response(
        cls, data: dict[str, Any], date: datetime.date
    ) -> Optional["WhoopRecoveryParser"]:
        """Parse Whoop API recovery response."""
        if not data:
            return None

        try:
            score_data = data.get("score", {})
            calibrating = score_data.get("user_calibrating", False)

            return cls(
                recovery_score=score_data.get("recovery_score"),
                resting_heart_rate=score_data.get("resting_heart_rate"),
                hrv_rmssd=score_data.get("hrv_rmssd_milli"),
                spo2_percentage=score_data.get("spo2_percentage"),
                skin_temp_celsius=score_data.get("skin_temp_celsius"),
                user_calibrating=1 if calibrating else 0,
            )
        except Exception as e:
            logger.error(f"Error parsing Whoop recovery data: {e}")
            return None


class WhoopSleepParser(BaseModel):
    """Pydantic model for parsing Whoop Sleep data."""

    sleep_performance_percentage: float | None = Field(
        None, description="Sleep performance %"
    )
    sleep_consistency_percentage: float | None = Field(
        None, description="Sleep consistency %"
    )
    sleep_efficiency_percentage: float | None = Field(
        None, description="Sleep efficiency %"
    )
    total_sleep_duration_minutes: int | None = Field(
        None, description="Total sleep in minutes"
    )
    deep_sleep_minutes: int | None = Field(None, description="Deep sleep in minutes")
    light_sleep_minutes: int | None = Field(None, description="Light sleep in minutes")
    rem_sleep_minutes: int | None = Field(None, description="REM sleep in minutes")
    awake_minutes: int | None = Field(None, description="Awake time in minutes")
    respiratory_rate: float | None = Field(None, description="Respiratory rate")

    @classmethod
    def from_whoop_response(
        cls, data: dict[str, Any], date: datetime.date
    ) -> Optional["WhoopSleepParser"]:
        """Parse Whoop API sleep response."""
        if not data:
            return None

        try:
            score_data = data.get("score", {})
            stage_summary = score_data.get("stage_summary", {})

            def millis_to_minutes(millis):
                return int(millis / 1000 / 60) if millis is not None else None

            return cls(
                sleep_performance_percentage=score_data.get(
                    "sleep_performance_percentage"
                ),
                sleep_consistency_percentage=score_data.get(
                    "sleep_consistency_percentage"
                ),
                sleep_efficiency_percentage=score_data.get(
                    "sleep_efficiency_percentage"
                ),
                total_sleep_duration_minutes=millis_to_minutes(
                    stage_summary.get("total_in_bed_time_milli")
                ),
                deep_sleep_minutes=millis_to_minutes(
                    stage_summary.get("total_slow_wave_sleep_time_milli")
                ),
                light_sleep_minutes=millis_to_minutes(
                    stage_summary.get("total_light_sleep_time_milli")
                ),
                rem_sleep_minutes=millis_to_minutes(
                    stage_summary.get("total_rem_sleep_time_milli")
                ),
                awake_minutes=millis_to_minutes(
                    stage_summary.get("total_awake_time_milli")
                ),
                respiratory_rate=score_data.get("respiratory_rate"),
            )
        except Exception as e:
            logger.error(f"Error parsing Whoop sleep data: {e}")
            return None


class WhoopWorkoutParser(BaseModel):
    """Pydantic model for parsing Whoop Workout data."""

    start_time: datetime.datetime = Field(..., description="Workout start time")
    strain: float | None = Field(None, description="Strain score")
    avg_heart_rate: int | None = Field(None, description="Average heart rate")
    max_heart_rate: int | None = Field(None, description="Maximum heart rate")
    kilojoules: float | None = Field(None, description="Energy in kilojoules")
    distance_meters: float | None = Field(None, description="Distance in meters")
    altitude_gain_meters: float | None = Field(
        None, description="Altitude gain in meters"
    )
    sport_name: str | None = Field(None, description="Sport/activity name")

    @classmethod
    def from_whoop_response(
        cls, data: dict[str, Any]
    ) -> Optional["WhoopWorkoutParser"]:
        """Parse Whoop API v2 workout response."""
        if not data:
            return None

        try:
            score_data = data.get("score", {})

            start_str = data.get("start")
            start_time = (
                datetime.datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                if start_str
                else None
            )

            if not start_time:
                return None

            return cls(
                start_time=start_time,
                strain=score_data.get("strain"),
                avg_heart_rate=score_data.get("average_heart_rate"),
                max_heart_rate=score_data.get("max_heart_rate"),
                kilojoules=score_data.get("kilojoule"),
                distance_meters=score_data.get("distance_meter"),
                altitude_gain_meters=score_data.get("altitude_gain_meter"),
                sport_name=data.get("sport_name"),
            )
        except Exception as e:
            logger.error(f"Error parsing Whoop workout data: {e}")
            return None


class WhoopCycleParser(BaseModel):
    """Pydantic model for parsing Whoop Cycle (daily summary) data."""

    strain: float | None = Field(None, description="Daily strain score (0-21)")
    kilojoules: float | None = Field(None, description="Daily energy expenditure in kJ")
    avg_heart_rate: int | None = Field(None, description="Average heart rate for day")
    max_heart_rate: int | None = Field(None, description="Maximum heart rate for day")

    @classmethod
    def from_whoop_response(
        cls, data: dict[str, Any], date: datetime.date
    ) -> Optional["WhoopCycleParser"]:
        """Parse Whoop API v2 cycle response."""
        if not data:
            return None

        try:
            score_data = data.get("score", {})

            return cls(
                strain=score_data.get("strain"),
                kilojoules=score_data.get("kilojoule"),
                avg_heart_rate=score_data.get("average_heart_rate"),
                max_heart_rate=score_data.get("max_heart_rate"),
            )
        except Exception as e:
            logger.error(f"Error parsing Whoop cycle data: {e}")
            return None
