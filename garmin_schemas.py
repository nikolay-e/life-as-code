"""
Pydantic models for robust Garmin Connect API data parsing.
Refactored with dynamic field mapping to reduce redundancy.
"""

import logging
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

logger = logging.getLogger(__name__)


class GarminBaseModel(BaseModel):
    """Base model with dynamic field mapping for Garmin API responses."""

    @classmethod
    def get_field_mappings(cls) -> dict[str, list[str]]:
        """Override this method to define field mappings for each model."""
        return {}

    @classmethod
    def from_garmin_response(cls, data: dict[str, Any]) -> Optional["GarminBaseModel"]:
        """Create instance from Garmin API response with flexible field mapping."""
        if not data:
            return None

        try:
            field_mappings = cls.get_field_mappings()
            parsed_data = {}

            # Map fields using the defined mappings
            for target_field, possible_source_fields in field_mappings.items():
                value = None
                for source_field in possible_source_fields:
                    if source_field in data and data[source_field] is not None:
                        value = data[source_field]
                        break
                parsed_data[target_field] = value

            # Add any additional direct mappings (fields not in mappings)
            for field_name, _field_info in cls.model_fields.items():
                if field_name not in parsed_data and field_name in data:
                    parsed_data[field_name] = data[field_name]

            return cls(**parsed_data)

        except Exception as e:
            logger.error(f"Error parsing {cls.__name__} from Garmin response: {e}")
            return None


class GarminSleepData(GarminBaseModel):
    """Pydantic model for Garmin sleep data with robust field handling."""

    # Core sleep metrics
    deep_sleep_duration: int | None = Field(
        None, description="Deep sleep duration in seconds"
    )
    light_sleep_duration: int | None = Field(
        None, description="Light sleep duration in seconds"
    )
    rem_sleep_duration: int | None = Field(
        None, description="REM sleep duration in seconds"
    )
    awake_duration: int | None = Field(None, description="Awake duration in seconds")
    total_sleep_time: int | None = Field(
        None, description="Total sleep time in seconds"
    )
    sleep_score: float | None = Field(None, description="Sleep quality score")

    # Enhanced sleep tracking fields
    body_battery_change: int | None = Field(
        None, description="Body battery charge change"
    )
    skin_temp_celsius: float | None = Field(
        None, description="Average skin temperature in Celsius"
    )
    awake_count: int | None = Field(None, description="Number of times awakened")
    sleep_quality_score: float | None = Field(None, description="Sleep quality score")
    sleep_recovery_score: float | None = Field(None, description="Sleep recovery score")
    spo2_avg: float | None = Field(None, description="Average SpO2 percentage")
    spo2_min: float | None = Field(None, description="Minimum SpO2 percentage")
    respiratory_rate: float | None = Field(None, description="Average respiratory rate")

    @classmethod
    def get_field_mappings(cls) -> dict[str, list[str]]:
        return {
            "deep_sleep_duration": [
                "deepSleepDuration",
                "deep_sleep_duration",
                "deepSleep",
                "deepSleepSeconds",
                "deepMinutes",
            ],
            "light_sleep_duration": [
                "lightSleepDuration",
                "light_sleep_duration",
                "lightSleep",
                "lightSleepSeconds",
                "lightMinutes",
            ],
            "rem_sleep_duration": [
                "remSleepDuration",
                "rem_sleep_duration",
                "remSleep",
                "remSleepSeconds",
                "remMinutes",
            ],
            "awake_duration": [
                "awakeDuration",
                "awake_duration",
                "awakeTime",
                "awakeSeconds",
                "awakeMinutes",
            ],
            "total_sleep_time": [
                "totalSleepTime",
                "total_sleep_time",
                "sleepTime",
                "totalSleepSeconds",
                "totalSleepMinutes",
            ],
            "sleep_score": ["sleepScore", "sleep_score", "overallScore", "score"],
            "body_battery_change": [
                "bodyBatteryChange",
                "body_battery_change",
                "bbChange",
            ],
            "skin_temp_celsius": [
                "avgSkinTempCelsius",
                "skin_temp_celsius",
                "skinTemp",
            ],
            "awake_count": ["awakeningsCount", "awake_count", "awakenings"],
            "sleep_quality_score": [
                "sleepQualityScore",
                "sleep_quality_score",
                "qualityScore",
            ],
            "sleep_recovery_score": [
                "sleepRecoveryScore",
                "sleep_recovery_score",
                "recoveryScore",
            ],
            "spo2_avg": ["avgSpO2", "spo2_avg", "oxygenSaturationAvg"],
            "spo2_min": ["lowestSpO2", "spo2_min", "oxygenSaturationMin"],
            "respiratory_rate": [
                "avgRespirationRate",
                "respiratory_rate",
                "respirationRate",
            ],
        }

    @field_validator(
        "deep_sleep_duration",
        "light_sleep_duration",
        "rem_sleep_duration",
        "awake_duration",
        "total_sleep_time",
        mode="before",
    )
    @classmethod
    def convert_duration_to_seconds(cls, v):
        """Convert various duration formats to seconds."""
        if v is None:
            return None
        if isinstance(v, int | float):
            return int(v)
        if isinstance(v, str):
            try:
                return int(float(v))
            except (ValueError, TypeError):
                return None
        return None

    @model_validator(mode="after")
    def validate_sleep_data(self):
        """Validate sleep data consistency."""
        # If total_sleep_time is missing, try to calculate it
        if self.total_sleep_time is None:
            components = [
                self.deep_sleep_duration or 0,
                self.light_sleep_duration or 0,
                self.rem_sleep_duration or 0,
            ]
            if any(x > 0 for x in components):
                self.total_sleep_time = sum(components)
        return self


class GarminHRVData(GarminBaseModel):
    """Pydantic model for Garmin HRV data."""

    hrv_avg: float | None = Field(None, description="Average HRV in milliseconds")
    hrv_status: str | None = Field(
        None, description="HRV status (BALANCED, UNBALANCED, etc.)"
    )
    baseline_low_ms: float | None = Field(
        None, description="Baseline low in milliseconds"
    )
    baseline_high_ms: float | None = Field(
        None, description="Baseline high in milliseconds"
    )
    feedback_phrase: str | None = Field(None, description="Feedback message")

    @classmethod
    def get_field_mappings(cls) -> dict[str, list[str]]:
        return {
            "hrv_avg": ["lastNightAvg", "hrv_avg", "weeklyAvg", "average", "avg"],
            "hrv_status": ["status", "hrv_status", "lastNightStatus", "balanceStatus"],
            "baseline_low_ms": ["baselineLowMs", "baseline_low_ms", "baselineLow"],
            "baseline_high_ms": ["baselineHighMs", "baseline_high_ms", "baselineHigh"],
            "feedback_phrase": [
                "feedbackPhrase",
                "feedback_phrase",
                "message",
                "feedback",
            ],
        }


class GarminStressData(GarminBaseModel):
    """Pydantic model for Garmin stress data."""

    avg_stress: float | None = Field(None, description="Average stress level")
    max_stress: float | None = Field(None, description="Maximum stress level")
    stress_level: str | None = Field(None, description="Stress level category")
    rest_stress: float | None = Field(None, description="Rest stress level")
    activity_stress: float | None = Field(None, description="Activity stress level")

    @classmethod
    def get_field_mappings(cls) -> dict[str, list[str]]:
        return {
            "avg_stress": [
                "overallStressLevel",
                "avg_stress",
                "averageStressLevel",
                "avgStress",
            ],
            "max_stress": [
                "maxStressLevel",
                "max_stress",
                "maximumStressLevel",
                "maxStress",
            ],
            "stress_level": [
                "stressLevelValue",
                "stress_level",
                "stressLevel",
                "level",
            ],
            "rest_stress": ["restStressLevel", "rest_stress", "restingStress"],
            "activity_stress": [
                "activityStressLevel",
                "activity_stress",
                "activeStress",
            ],
        }


class GarminStepsData(GarminBaseModel):
    """Pydantic model for Garmin steps data."""

    total_steps: int | None = Field(None, description="Total steps for the day")
    total_distance: float | None = Field(None, description="Total distance in meters")
    step_goal: int | None = Field(None, description="Daily step goal")
    active_minutes: int | None = Field(None, description="Active minutes")
    floors_climbed: int | None = Field(None, description="Floors climbed")

    @classmethod
    def get_field_mappings(cls) -> dict[str, list[str]]:
        return {
            "total_steps": ["totalSteps", "total_steps", "steps", "dailySteps"],
            "total_distance": [
                "totalDistance",
                "total_distance",
                "distance",
                "distanceMeters",
            ],
            "step_goal": ["stepGoal", "step_goal", "goal", "dailyStepGoal"],
            "active_minutes": ["activeMinutes", "active_minutes", "vigorousMinutes"],
            "floors_climbed": ["floorsClimbed", "floors_climbed", "floors"],
        }


class GarminWeightData(GarminBaseModel):
    """Pydantic model for Garmin weight and body composition data."""

    weight_kg: float | None = Field(None, description="Weight in kilograms")
    bmi: float | None = Field(None, description="Body Mass Index")
    body_fat_pct: float | None = Field(None, description="Body fat percentage")
    muscle_mass_kg: float | None = Field(None, description="Muscle mass in kilograms")
    bone_mass_kg: float | None = Field(None, description="Bone mass in kilograms")
    water_pct: float | None = Field(None, description="Body water percentage")

    @classmethod
    def get_field_mappings(cls) -> dict[str, list[str]]:
        return {
            "weight_kg": ["weight", "weight_kg", "weightKg", "bodyWeight"],
            "bmi": ["bmi", "bodyMassIndex"],
            "body_fat_pct": [
                "bodyFat",
                "body_fat_pct",
                "bodyFatPercentage",
                "fatPercentage",
            ],
            "muscle_mass_kg": ["muscleMass", "muscle_mass_kg", "muscleMassKg"],
            "bone_mass_kg": ["boneMass", "bone_mass_kg", "boneMassKg"],
            "water_pct": [
                "bodyWater",
                "water_pct",
                "waterPercentage",
                "bodyWaterPercentage",
            ],
        }


class GarminHeartRateData(GarminBaseModel):
    """Pydantic model for Garmin heart rate data."""

    resting_hr: int | None = Field(None, description="Resting heart rate")
    max_hr: int | None = Field(None, description="Maximum heart rate")
    avg_hr: int | None = Field(None, description="Average heart rate")

    @classmethod
    def get_field_mappings(cls) -> dict[str, list[str]]:
        return {
            "resting_hr": ["restingHeartRate", "resting_hr", "restingHR", "restHR"],
            "max_hr": ["maxHeartRate", "max_hr", "maximumHR", "maxHR"],
            "avg_hr": ["averageHeartRate", "avg_hr", "avgHR", "meanHR"],
        }
