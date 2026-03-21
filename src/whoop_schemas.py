import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from date_utils import parse_iso_datetime
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
    user_calibrating: bool = False

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
                user_calibrating=bool(calibrating),
            )
        except Exception as e:
            logger.error("whoop_recovery_parse_error", error=str(e))
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
    sleep_need_baseline_minutes: int | None = Field(None)
    sleep_need_debt_minutes: int | None = Field(None)
    sleep_need_strain_minutes: int | None = Field(None)
    sleep_need_nap_minutes: int | None = Field(None)
    sleep_cycle_count: int | None = Field(None)
    disturbance_count: int | None = Field(None)
    no_data_minutes: int | None = Field(None)

    @classmethod
    def from_whoop_response(
        cls, data: dict[str, Any], date: datetime.date
    ) -> Optional["WhoopSleepParser"]:
        if not data:
            return None

        try:
            score_data = data.get("score", {})
            stage_summary = score_data.get("stage_summary", {})
            sleep_needed = score_data.get("sleep_needed", {})

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
                sleep_need_baseline_minutes=millis_to_minutes(
                    sleep_needed.get("baseline_milli")
                ),
                sleep_need_debt_minutes=millis_to_minutes(
                    sleep_needed.get("need_from_sleep_debt_milli")
                ),
                sleep_need_strain_minutes=millis_to_minutes(
                    sleep_needed.get("need_from_recent_strain_milli")
                ),
                sleep_need_nap_minutes=millis_to_minutes(
                    sleep_needed.get("need_from_recent_nap_milli")
                ),
                sleep_cycle_count=stage_summary.get("sleep_cycle_count"),
                disturbance_count=stage_summary.get("disturbance_count"),
                no_data_minutes=millis_to_minutes(
                    stage_summary.get("total_no_data_time_milli")
                ),
            )
        except Exception as e:
            logger.error("whoop_sleep_parse_error", error=str(e))
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
    end_time: datetime.datetime | None = Field(None)
    percent_recorded: float | None = Field(None)
    altitude_change_meters: float | None = Field(None)
    zone_zero_millis: int | None = Field(None)
    zone_one_millis: int | None = Field(None)
    zone_two_millis: int | None = Field(None)
    zone_three_millis: int | None = Field(None)
    zone_four_millis: int | None = Field(None)
    zone_five_millis: int | None = Field(None)

    @classmethod
    def from_whoop_response(
        cls, data: dict[str, Any]
    ) -> Optional["WhoopWorkoutParser"]:
        if not data:
            return None

        try:
            score_data = data.get("score", {})
            zone_durations = score_data.get("zone_duration", {})

            start_str = data.get("start")
            start_time = parse_iso_datetime(start_str) if start_str else None

            if not start_time:
                return None

            end_str = data.get("end")
            end_time = parse_iso_datetime(end_str) if end_str else None

            return cls(
                start_time=start_time,
                end_time=end_time,
                strain=score_data.get("strain"),
                avg_heart_rate=score_data.get("average_heart_rate"),
                max_heart_rate=score_data.get("max_heart_rate"),
                kilojoules=score_data.get("kilojoule"),
                distance_meters=score_data.get("distance_meter"),
                altitude_gain_meters=score_data.get("altitude_gain_meter"),
                sport_name=data.get("sport_name"),
                percent_recorded=score_data.get("percent_recorded"),
                altitude_change_meters=score_data.get("altitude_change_meter"),
                zone_zero_millis=zone_durations.get("zone_zero_milli"),
                zone_one_millis=zone_durations.get("zone_one_milli"),
                zone_two_millis=zone_durations.get("zone_two_milli"),
                zone_three_millis=zone_durations.get("zone_three_milli"),
                zone_four_millis=zone_durations.get("zone_four_milli"),
                zone_five_millis=zone_durations.get("zone_five_milli"),
            )
        except Exception as e:
            logger.error("whoop_workout_parse_error", error=str(e))
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
            logger.error("whoop_cycle_parse_error", error=str(e))
            return None
