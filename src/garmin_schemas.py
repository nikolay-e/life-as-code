import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from logging_config import get_logger

logger = get_logger(__name__)


class GarminBaseModel(BaseModel):
    """Base model with dynamic field mapping for Garmin API responses."""

    date: datetime.date | None = Field(None, description="Date of the data record")

    @classmethod
    def get_field_mappings(cls) -> dict[str, list[str]]:
        """Override this method to define field mappings for each model."""
        return {"date": ["date", "calendarDate", "measurementDate", "summaryDate"]}

    @classmethod
    def from_garmin_response(cls, data: dict[str, Any]) -> Optional["GarminBaseModel"]:
        """Create instance from Garmin API response with flexible field mapping."""
        if not data:
            return None

        try:
            # Merge base class mappings with subclass mappings
            base_mappings = GarminBaseModel.get_field_mappings()
            subclass_mappings = cls.get_field_mappings()
            field_mappings = {**base_mappings, **subclass_mappings}
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
            logger.error("garmin_parse_error", model=cls.__name__, error=str(e))
            return None


class GarminSleepData(GarminBaseModel):
    """Pydantic model for Garmin sleep data with robust field handling."""

    # Core sleep metrics (field names match Sleep SQLAlchemy model)
    deep_minutes: float | None = Field(
        None, description="Deep sleep duration in minutes"
    )
    light_minutes: float | None = Field(
        None, description="Light sleep duration in minutes"
    )
    rem_minutes: float | None = Field(None, description="REM sleep duration in minutes")
    awake_minutes: float | None = Field(None, description="Awake duration in minutes")
    total_sleep_minutes: float | None = Field(
        None, description="Total sleep time in minutes"
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
            "deep_minutes": [
                "deepSleepSeconds",
                "deepSleepDuration",
                "deep_sleep_duration",
                "deepSleep",
                "deepMinutes",
            ],
            "light_minutes": [
                "lightSleepSeconds",
                "lightSleepDuration",
                "light_sleep_duration",
                "lightSleep",
                "lightMinutes",
            ],
            "rem_minutes": [
                "remSleepSeconds",
                "remSleepDuration",
                "rem_sleep_duration",
                "remSleep",
                "remMinutes",
            ],
            "awake_minutes": [
                "awakeSeconds",
                "awakeDuration",
                "awake_duration",
                "awakeTime",
                "awakeMinutes",
            ],
            "total_sleep_minutes": [
                "sleepTimeSeconds",
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
        "deep_minutes",
        "light_minutes",
        "rem_minutes",
        "awake_minutes",
        "total_sleep_minutes",
        mode="before",
    )
    @classmethod
    def convert_duration_to_minutes(cls, v):
        """Convert duration from seconds to minutes for database storage.

        Garmin API always returns sleep durations in seconds.
        """
        if v is None:
            return None
        try:
            val = float(v)
        except (ValueError, TypeError):
            return None

        return val / 60.0

    @field_validator("spo2_avg", "spo2_min", mode="before")
    @classmethod
    def validate_spo2(cls, v):
        """Validate SpO2 values are within valid range (50-100%)."""
        if v is None:
            return None
        try:
            val = float(v)
            # Valid SpO2 range: 50-100%
            if val < 50 or val > 100:
                return None
            return val
        except (ValueError, TypeError):
            return None

    @field_validator("respiratory_rate", mode="before")
    @classmethod
    def validate_respiratory_rate(cls, v):
        """Validate respiratory rate is within valid range (5-40 breaths/min)."""
        if v is None:
            return None
        try:
            val = float(v)
            # Valid respiratory rate: 5-40 breaths/min
            if val < 5 or val > 40:
                return None
            return val
        except (ValueError, TypeError):
            return None

    @field_validator(
        "sleep_score", "sleep_quality_score", "sleep_recovery_score", mode="before"
    )
    @classmethod
    def validate_sleep_scores(cls, v):
        """Validate sleep scores are within 0-100 range."""
        if v is None:
            return None
        try:
            val = float(v)
            if val < 0:
                return 0.0
            if val > 100:
                return 100.0
            return val
        except (ValueError, TypeError):
            return None

    @field_validator("skin_temp_celsius", mode="before")
    @classmethod
    def validate_skin_temp(cls, v):
        """Validate skin temperature is within reasonable range."""
        if v is None:
            return None
        try:
            val = float(v)
            # Valid skin temp range: 25-45 Celsius
            if val < 25 or val > 45:
                return None
            return val
        except (ValueError, TypeError):
            return None

    @model_validator(mode="after")
    def validate_sleep_data(self):
        """Validate sleep data consistency."""
        # If total_sleep_minutes is missing, try to calculate it
        if self.total_sleep_minutes is None:
            components = [
                self.deep_minutes or 0,
                self.light_minutes or 0,
                self.rem_minutes or 0,
            ]
            if any(x > 0 for x in components):
                self.total_sleep_minutes = sum(components)
        return self


class GarminHRVData(GarminBaseModel):
    """Pydantic model for Garmin HRV data."""

    hrv_avg: float | None = Field(None, description="Average HRV in milliseconds")
    hrv_status: str | None = Field(
        None, description="HRV status (BALANCED, UNBALANCED, LOW, etc.)"
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
            "hrv_avg": [
                "lastNightAvg",
                "hrv_avg",
                "weeklyAvg",
                "average",
                "avg",
                "lastNightAverage",
            ],
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

    @field_validator("hrv_avg", "baseline_low_ms", "baseline_high_ms", mode="before")
    @classmethod
    def validate_hrv_values(cls, v):
        """Validate HRV values are positive and within reasonable range."""
        if v is None:
            return None
        try:
            val = float(v)
            # HRV in ms is typically 10-200ms range
            if val < 0:
                return None
            if val > 500:
                return None  # Unrealistic HRV value
            return val
        except (ValueError, TypeError):
            return None

    @field_validator("hrv_status", mode="before")
    @classmethod
    def normalize_hrv_status(cls, v):
        """Normalize HRV status to uppercase."""
        if v is None:
            return None
        if isinstance(v, str):
            return v.upper().strip()
        return str(v).upper()


class GarminStressData(GarminBaseModel):
    """Pydantic model for Garmin stress data."""

    avg_stress: float | None = Field(None, description="Average stress level (0-100)")
    max_stress: float | None = Field(None, description="Maximum stress level (0-100)")
    stress_level: str | None = Field(None, description="Stress level category")
    rest_stress: float | None = Field(None, description="Rest stress level (0-100)")
    activity_stress: float | None = Field(
        None, description="Activity stress level (0-100)"
    )

    @classmethod
    def get_field_mappings(cls) -> dict[str, list[str]]:
        return {
            "avg_stress": [
                "overallStressLevel",
                "avg_stress",
                "averageStressLevel",
                "avgStress",
                "avgStressLevel",
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

    @field_validator(
        "avg_stress", "max_stress", "rest_stress", "activity_stress", mode="before"
    )
    @classmethod
    def validate_stress_level(cls, v):
        """Validate stress level is within 0-100 range."""
        if v is None:
            return None
        try:
            stress = float(v)
            # Clamp to valid range
            if stress < 0:
                return 0.0
            if stress > 100:
                return 100.0
            return stress
        except (ValueError, TypeError):
            return None

    @field_validator("stress_level", mode="before")
    @classmethod
    def normalize_stress_category(cls, v):
        """Normalize stress level category."""
        if v is None:
            return None
        if isinstance(v, str):
            normalized = v.upper().strip()
            # Map common variations to standard values
            mapping = {
                "LOW": "low",
                "MEDIUM": "medium",
                "MED": "medium",
                "MODERATE": "medium",
                "HIGH": "high",
            }
            return mapping.get(normalized, v.lower())
        return str(v).lower()


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
                "totalDistanceMeters",
            ],
            "step_goal": ["stepGoal", "step_goal", "goal", "dailyStepGoal"],
            "active_minutes": [
                "activeMinutes",
                "active_minutes",
                "vigorousMinutes",
                "moderateIntensityMinutes",
            ],
            "floors_climbed": [
                "floorsClimbed",
                "floors_climbed",
                "floors",
                "floorsAscended",
            ],
        }

    @field_validator(
        "total_steps", "step_goal", "active_minutes", "floors_climbed", mode="before"
    )
    @classmethod
    def coerce_to_int(cls, v):
        """Safely convert values to int."""
        if v is None:
            return None
        try:
            return int(v)
        except (ValueError, TypeError):
            return None

    @field_validator("total_distance", mode="before")
    @classmethod
    def coerce_to_float(cls, v):
        """Safely convert distance to float."""
        if v is None:
            return None
        try:
            return float(v)
        except (ValueError, TypeError):
            return None


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
                "percentFat",
            ],
            "muscle_mass_kg": ["muscleMass", "muscle_mass_kg", "muscleMassKg"],
            "bone_mass_kg": ["boneMass", "bone_mass_kg", "boneMassKg"],
            "water_pct": [
                "bodyWater",
                "water_pct",
                "waterPercentage",
                "bodyWaterPercentage",
                "percentHydration",
            ],
        }

    @field_validator("weight_kg", mode="before")
    @classmethod
    def convert_weight_to_kg(cls, v):
        """Convert weight to kg. API may return grams (large values) or kg."""
        if v is None:
            return None
        try:
            weight = float(v)
            # If weight > 500, assume it's in grams and convert to kg
            if weight > 500:
                return weight / 1000.0
            return weight
        except (ValueError, TypeError):
            return None

    @field_validator("muscle_mass_kg", "bone_mass_kg", mode="before")
    @classmethod
    def convert_mass_to_kg(cls, v):
        """Convert mass values to kg. API may return grams."""
        if v is None:
            return None
        try:
            mass = float(v)
            # If mass > 100, assume it's in grams
            if mass > 100:
                return mass / 1000.0
            return mass
        except (ValueError, TypeError):
            return None

    @field_validator("bmi", "body_fat_pct", "water_pct", mode="before")
    @classmethod
    def coerce_percentage(cls, v):
        """Safely convert percentage values."""
        if v is None:
            return None
        try:
            val = float(v)
            # Clamp percentages to valid range
            if val < 0:
                return 0.0
            if val > 100:
                return 100.0
            return val
        except (ValueError, TypeError):
            return None


class GarminHeartRateData(GarminBaseModel):
    """Pydantic model for Garmin heart rate data."""

    resting_hr: int | None = Field(None, description="Resting heart rate in BPM")
    max_hr: int | None = Field(None, description="Maximum heart rate in BPM")
    avg_hr: int | None = Field(None, description="Average heart rate in BPM")
    spo2_avg: float | None = Field(None)
    spo2_min: float | None = Field(None)
    waking_respiratory_rate: float | None = Field(None)
    lowest_respiratory_rate: float | None = Field(None)
    highest_respiratory_rate: float | None = Field(None)

    @classmethod
    def get_field_mappings(cls) -> dict[str, list[str]]:
        return {
            "resting_hr": [
                "restingHeartRate",
                "resting_hr",
                "restingHR",
                "restHR",
                "lastSevenDaysAvgRestingHeartRate",
            ],
            "max_hr": ["maxHeartRate", "max_hr", "maximumHR", "maxHR"],
            "avg_hr": ["averageHeartRate", "avg_hr", "avgHR", "meanHR"],
            "spo2_avg": ["averageSpO2", "spo2_avg"],
            "spo2_min": ["lowestSpO2", "spo2_min"],
            "waking_respiratory_rate": [
                "avgWakingRespirationValue",
                "waking_respiratory_rate",
            ],
            "lowest_respiratory_rate": [
                "lowestRespirationValue",
                "lowest_respiratory_rate",
            ],
            "highest_respiratory_rate": [
                "highestRespirationValue",
                "highest_respiratory_rate",
            ],
        }

    @field_validator("resting_hr", "max_hr", "avg_hr", mode="before")
    @classmethod
    def validate_heart_rate(cls, v):
        if v is None:
            return None
        try:
            hr = int(float(v))
            if hr < 20 or hr > 300:
                return None
            return hr
        except (ValueError, TypeError):
            return None

    @field_validator("spo2_avg", "spo2_min", mode="before")
    @classmethod
    def validate_spo2(cls, v):
        if v is None:
            return None
        try:
            val = float(v)
            if val < 50 or val > 100:
                return None
            return val
        except (ValueError, TypeError):
            return None

    @field_validator(
        "waking_respiratory_rate",
        "lowest_respiratory_rate",
        "highest_respiratory_rate",
        mode="before",
    )
    @classmethod
    def validate_respiratory_rate(cls, v):
        if v is None:
            return None
        try:
            val = float(v)
            if val < 5 or val > 50:
                return None
            return val
        except (ValueError, TypeError):
            return None


class GarminTrainingStatusData(GarminBaseModel):
    """Pydantic model for Garmin training status, VO2Max, and fitness metrics."""

    vo2_max: float | None = Field(None, description="VO2 Max value")
    vo2_max_precise: float | None = Field(None, description="Precise VO2 Max value")
    fitness_age: int | None = Field(None, description="Fitness age in years")
    training_load_7_day: float | None = Field(None, description="7-day training load")
    acute_training_load: float | None = Field(None, description="Acute training load")
    training_status: str | None = Field(None, description="Training status label")
    training_status_description: str | None = Field(
        None, description="Training status description"
    )
    primary_training_effect: float | None = Field(
        None, description="Primary training effect (1-5)"
    )
    anaerobic_training_effect: float | None = Field(
        None, description="Anaerobic training effect (1-5)"
    )
    endurance_score: float | None = Field(None, description="Endurance score (0-100)")
    training_readiness_score: float | None = Field(
        None, description="Training readiness score (0-100)"
    )
    total_kilocalories: float | None = Field(
        None, description="Total daily kilocalories"
    )
    active_kilocalories: float | None = Field(
        None, description="Active kilocalories burned"
    )

    @classmethod
    def get_field_mappings(cls) -> dict[str, list[str]]:
        return {
            "vo2_max": [
                "vo2MaxValue",
                "vo2Max",
                "vo2_max",
                "maxMetValue",
                "fitnessVO2Max",
            ],
            "vo2_max_precise": [
                "vo2MaxPreciseValue",
                "vo2MaxPrecise",
                "vo2_max_precise",
            ],
            "fitness_age": [
                "fitnessAge",
                "fitness_age",
                "chronologicalAge",
                "fitAge",
            ],
            "training_load_7_day": [
                "trainingLoad7Days",
                "dailyTrainingLoadChronic",
                "sevenDayTrainingLoad",
                "training_load_7_day",
                "weeklyTrainingLoad",
            ],
            "acute_training_load": [
                "acuteTrainingLoad",
                "dailyTrainingLoadAcute",
                "acute_training_load",
                "acuteLoad",
                "atl",
            ],
            "training_status": [
                "trainingStatusLabel",
                "training_status",
                "trainingStatus",
                "status",
            ],
            "training_status_description": [
                "trainingStatusDescription",
                "training_status_description",
                "statusDescription",
            ],
            "primary_training_effect": [
                "primaryTrainingEffect",
                "primary_training_effect",
                "aerobicTrainingEffect",
            ],
            "anaerobic_training_effect": [
                "anaerobicTrainingEffect",
                "anaerobic_training_effect",
            ],
            "endurance_score": [
                "enduranceScore",
                "endurance_score",
                "cardioScore",
            ],
            "training_readiness_score": [
                "trainingReadinessScore",
                "training_readiness_score",
                "score",
            ],
            "total_kilocalories": [
                "totalKilocalories",
                "total_kilocalories",
                "totalCalories",
                "dailyCalories",
            ],
            "active_kilocalories": [
                "activeKilocalories",
                "active_kilocalories",
                "activeCalories",
                "activityCalories",
            ],
        }

    @field_validator("vo2_max", "vo2_max_precise", mode="before")
    @classmethod
    def validate_vo2_max(cls, v):
        if v is None:
            return None
        try:
            val = float(v)
            if val < 10 or val > 100:
                return None
            return val
        except (ValueError, TypeError):
            return None

    @field_validator("fitness_age", mode="before")
    @classmethod
    def validate_fitness_age(cls, v):
        if v is None:
            return None
        try:
            age = int(float(v))
            if age < 10 or age > 120:
                return None
            return age
        except (ValueError, TypeError):
            return None

    @field_validator(
        "training_load_7_day",
        "acute_training_load",
        "total_kilocalories",
        "active_kilocalories",
        mode="before",
    )
    @classmethod
    def validate_positive_float(cls, v):
        if v is None:
            return None
        try:
            val = float(v)
            if val < 0:
                return 0.0
            return val
        except (ValueError, TypeError):
            return None

    @field_validator(
        "primary_training_effect", "anaerobic_training_effect", mode="before"
    )
    @classmethod
    def validate_training_effect(cls, v):
        if v is None:
            return None
        try:
            val = float(v)
            if val < 0 or val > 5:
                return None
            return val
        except (ValueError, TypeError):
            return None

    @field_validator("endurance_score", "training_readiness_score", mode="before")
    @classmethod
    def validate_score_0_100(cls, v):
        if v is None:
            return None
        try:
            val = float(v)
            if val < 0:
                return 0.0
            if val > 100:
                return 100.0
            return val
        except (ValueError, TypeError):
            return None

    @field_validator("training_status", "training_status_description", mode="before")
    @classmethod
    def validate_string(cls, v):
        if v is None:
            return None
        return str(v).strip()[:200]


class GarminEnergyData(GarminBaseModel):
    active_energy: float | None = Field(None)
    basal_energy: float | None = Field(None)

    @classmethod
    def get_field_mappings(cls) -> dict[str, list[str]]:
        return {
            "active_energy": ["activeKilocalories", "active_energy", "activeCalories"],
            "basal_energy": ["bmrKilocalories", "basal_energy", "basalCalories"],
        }

    @field_validator("active_energy", "basal_energy", mode="before")
    @classmethod
    def validate_energy(cls, v):
        if v is None:
            return None
        try:
            val = float(v)
            if val < 0:
                return 0.0
            return val
        except (ValueError, TypeError):
            return None


class GarminActivityData(GarminBaseModel):
    """Pydantic model for Garmin activity data."""

    activity_id: str | None = Field(None, description="Unique activity identifier")
    start_time: datetime.datetime | None = Field(
        None, description="Activity start time"
    )
    activity_type: str | None = Field(
        None, description="Activity type (running, cycling, etc.)"
    )
    activity_name: str | None = Field(None, description="Activity name/title")
    duration_seconds: int | None = Field(None, description="Duration in seconds")
    distance_meters: float | None = Field(None, description="Distance in meters")
    avg_heart_rate: int | None = Field(None, description="Average heart rate in BPM")
    max_heart_rate: int | None = Field(None, description="Maximum heart rate in BPM")
    calories: int | None = Field(None, description="Calories burned")
    avg_speed_mps: float | None = Field(None, description="Average speed in m/s")
    max_speed_mps: float | None = Field(None, description="Maximum speed in m/s")
    elevation_gain_meters: float | None = Field(
        None, description="Elevation gain in meters"
    )
    elevation_loss_meters: float | None = Field(
        None, description="Elevation loss in meters"
    )
    avg_power_watts: float | None = Field(None, description="Average power in watts")
    max_power_watts: float | None = Field(None, description="Maximum power in watts")
    training_effect_aerobic: float | None = Field(
        None, description="Aerobic training effect (0-5)"
    )
    training_effect_anaerobic: float | None = Field(
        None, description="Anaerobic training effect (0-5)"
    )
    vo2_max_value: float | None = Field(None, description="VO2 Max value from activity")
    hr_zone_one_seconds: int | None = Field(None)
    hr_zone_two_seconds: int | None = Field(None)
    hr_zone_three_seconds: int | None = Field(None)
    hr_zone_four_seconds: int | None = Field(None)
    hr_zone_five_seconds: int | None = Field(None)

    @classmethod
    def get_field_mappings(cls) -> dict[str, list[str]]:
        return {
            "activity_id": ["activityId", "activity_id", "id"],
            "start_time": [
                "startTimeLocal",
                "startTimeGMT",
                "start_time",
                "beginTimestamp",
            ],
            "activity_type": [
                "activityType",
                "activity_type",
                "sportTypeId",
                "typeKey",
            ],
            "activity_name": ["activityName", "activity_name", "name"],
            "duration_seconds": [
                "duration",
                "duration_seconds",
                "elapsedDuration",
                "movingDuration",
            ],
            "distance_meters": ["distance", "distance_meters", "totalDistance"],
            "avg_heart_rate": [
                "averageHR",
                "avg_heart_rate",
                "avgHeartRate",
                "averageHeartRate",
            ],
            "max_heart_rate": [
                "maxHR",
                "max_heart_rate",
                "maxHeartRate",
                "maximumHeartRate",
            ],
            "calories": ["calories", "activeKilocalories", "kilocalories"],
            "avg_speed_mps": ["averageSpeed", "avg_speed_mps", "avgSpeed"],
            "max_speed_mps": ["maxSpeed", "max_speed_mps", "maximumSpeed"],
            "elevation_gain_meters": [
                "elevationGain",
                "elevation_gain_meters",
                "totalAscent",
                "ascent",
            ],
            "elevation_loss_meters": [
                "elevationLoss",
                "elevation_loss_meters",
                "totalDescent",
                "descent",
            ],
            "avg_power_watts": ["avgPower", "avg_power_watts", "averagePower"],
            "max_power_watts": ["maxPower", "max_power_watts", "maximumPower"],
            "training_effect_aerobic": [
                "aerobicTrainingEffect",
                "training_effect_aerobic",
                "trainingEffectLabel",
            ],
            "training_effect_anaerobic": [
                "anaerobicTrainingEffect",
                "training_effect_anaerobic",
            ],
            "vo2_max_value": ["vO2MaxValue", "vo2_max_value", "vo2Max"],
            "hr_zone_one_seconds": ["hr_zone_one_seconds"],
            "hr_zone_two_seconds": ["hr_zone_two_seconds"],
            "hr_zone_three_seconds": ["hr_zone_three_seconds"],
            "hr_zone_four_seconds": ["hr_zone_four_seconds"],
            "hr_zone_five_seconds": ["hr_zone_five_seconds"],
        }

    @field_validator("activity_id", mode="before")
    @classmethod
    def coerce_activity_id(cls, v):
        if v is None:
            return None
        return str(v)

    @field_validator("start_time", mode="before")
    @classmethod
    def parse_start_time(cls, v):
        if v is None:
            return None
        if isinstance(v, datetime.datetime):
            return v
        if isinstance(v, str):
            try:
                return datetime.datetime.fromisoformat(v.replace("Z", "+00:00"))
            except ValueError:
                pass
            try:
                return datetime.datetime.strptime(v, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                pass
        if isinstance(v, (int, float)):
            try:
                return datetime.datetime.fromtimestamp(v / 1000)
            except (ValueError, OSError):
                pass
        return None

    @field_validator("activity_type", mode="before")
    @classmethod
    def extract_activity_type(cls, v):
        if v is None:
            return None
        if isinstance(v, dict):
            return v.get("typeKey") or v.get("typeId") or str(v)
        return str(v).strip()[:100]

    @field_validator("activity_name", mode="before")
    @classmethod
    def validate_activity_name(cls, v):
        if v is None:
            return None
        return str(v).strip()[:200]

    @field_validator("duration_seconds", mode="before")
    @classmethod
    def convert_duration(cls, v):
        if v is None:
            return None
        try:
            val = float(v)
            if val < 0:
                return None
            return int(val)
        except (ValueError, TypeError):
            return None

    @field_validator(
        "distance_meters",
        "avg_speed_mps",
        "max_speed_mps",
        "elevation_gain_meters",
        "elevation_loss_meters",
        mode="before",
    )
    @classmethod
    def validate_positive_float(cls, v):
        if v is None:
            return None
        try:
            val = float(v)
            if val < 0:
                return None
            return val
        except (ValueError, TypeError):
            return None

    @field_validator("avg_heart_rate", "max_heart_rate", mode="before")
    @classmethod
    def validate_heart_rate(cls, v):
        if v is None:
            return None
        try:
            hr = int(float(v))
            if hr < 20 or hr > 300:
                return None
            return hr
        except (ValueError, TypeError):
            return None

    @field_validator("calories", mode="before")
    @classmethod
    def validate_calories(cls, v):
        if v is None:
            return None
        try:
            cal = int(float(v))
            if cal < 0:
                return None
            return cal
        except (ValueError, TypeError):
            return None

    @field_validator("avg_power_watts", "max_power_watts", mode="before")
    @classmethod
    def validate_power(cls, v):
        if v is None:
            return None
        try:
            val = float(v)
            if val < 0 or val > 3000:
                return None
            return val
        except (ValueError, TypeError):
            return None

    @field_validator(
        "training_effect_aerobic", "training_effect_anaerobic", mode="before"
    )
    @classmethod
    def validate_training_effect(cls, v):
        if v is None:
            return None
        try:
            val = float(v)
            if val < 0 or val > 5:
                return None
            return val
        except (ValueError, TypeError):
            return None

    @field_validator(
        "hr_zone_one_seconds",
        "hr_zone_two_seconds",
        "hr_zone_three_seconds",
        "hr_zone_four_seconds",
        "hr_zone_five_seconds",
        mode="before",
    )
    @classmethod
    def validate_hr_zone(cls, v):
        if v is None:
            return None
        try:
            val = int(float(v))
            if val < 0:
                return None
            return val
        except (ValueError, TypeError):
            return None

    @field_validator("vo2_max_value", mode="before")
    @classmethod
    def validate_vo2_max(cls, v):
        if v is None:
            return None
        try:
            val = float(v)
            if val < 10 or val > 100:
                return None
            return val
        except (ValueError, TypeError):
            return None


class GarminRacePredictionData(GarminBaseModel):
    prediction_5k_seconds: int | None = Field(None)
    prediction_10k_seconds: int | None = Field(None)
    prediction_half_marathon_seconds: int | None = Field(None)
    prediction_marathon_seconds: int | None = Field(None)
    vo2_max_value: float | None = Field(None)

    @classmethod
    def get_field_mappings(cls) -> dict[str, list[str]]:
        return {
            "prediction_5k_seconds": ["prediction_5k_seconds"],
            "prediction_10k_seconds": ["prediction_10k_seconds"],
            "prediction_half_marathon_seconds": ["prediction_half_marathon_seconds"],
            "prediction_marathon_seconds": ["prediction_marathon_seconds"],
            "vo2_max_value": ["vo2MaxValue", "vo2_max_value", "vo2Max"],
        }

    @field_validator(
        "prediction_5k_seconds",
        "prediction_10k_seconds",
        "prediction_half_marathon_seconds",
        "prediction_marathon_seconds",
        mode="before",
    )
    @classmethod
    def validate_prediction_seconds(cls, v):
        if v is None:
            return None
        try:
            val = int(float(v))
            if val <= 0:
                return None
            return val
        except (ValueError, TypeError):
            return None

    @field_validator("vo2_max_value", mode="before")
    @classmethod
    def validate_vo2_max(cls, v):
        if v is None:
            return None
        try:
            val = float(v)
            if val < 10 or val > 100:
                return None
            return val
        except (ValueError, TypeError):
            return None
