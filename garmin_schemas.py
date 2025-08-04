"""
Pydantic models for robust Garmin Connect API data parsing.
Handles schema variations and missing fields gracefully.
"""

from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class GarminSleepData(BaseModel):
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

    # New fields for enhanced sleep tracking
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

    # Validation and conversion
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

    @classmethod
    def from_garmin_response(cls, data: dict[str, Any]) -> Optional["GarminSleepData"]:
        """Create from Garmin API response with flexible field mapping."""
        if not data:
            return None

        try:
            # Map various possible field names from Garmin API
            field_mappings = {
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
                    "totalMinutes",
                ],
                "sleep_score": ["sleepScore", "sleep_score", "overallScore", "score"],
                "body_battery_change": [
                    "bodyBatteryChange",
                    "bodyBatteryDrain",
                    "batteryChange",
                ],
                "skin_temp_celsius": [
                    "skinTempCelsius",
                    "avgSkinTempCelsius",
                    "skinTemp",
                ],
                "awake_count": ["awakeCount", "awakeDuringSleep", "numberOfAwakenings"],
                "sleep_quality_score": [
                    "sleepQualityScore",
                    "qualityScore",
                    "sleepScores",
                ],
                "sleep_recovery_score": ["sleepRecoveryScore", "recoveryScore"],
                "spo2_avg": [
                    "avgSpO2",
                    "averageSpO2",
                    "oxygenSaturation",
                    "avgOxygenSaturation",
                ],
                "spo2_min": ["lowestSpO2", "minSpO2", "minimumSpO2"],
                "respiratory_rate": [
                    "avgRespiratoryRate",
                    "averageRespRate",
                    "respiratoryRate",
                ],
            }

            parsed_data = {}
            for field, possible_keys in field_mappings.items():
                value = None
                for key in possible_keys:
                    if key in data and data[key] is not None:
                        value = data[key]
                        # Convert minutes to seconds if needed
                        if "minutes" in key.lower() or "Minutes" in key:
                            if isinstance(value, int | float):
                                value = int(value * 60)
                        break
                parsed_data[field] = value

            return cls(**parsed_data)

        except Exception as e:
            # Log the error but don't fail the entire sync
            print(f"Warning: Could not parse sleep data: {e}")
            return None


class GarminHRVData(BaseModel):
    """Pydantic model for Garmin HRV data."""

    hrv_rmssd: float | None = Field(None, description="HRV RMSSD value")
    hrv_sdrr: float | None = Field(None, description="HRV SDRR value")
    hrv_score: float | None = Field(None, description="HRV readiness score")

    @classmethod
    def from_garmin_response(cls, data: dict[str, Any]) -> Optional["GarminHRVData"]:
        """Create from Garmin API response."""
        if not data:
            return None

        try:
            # Check for the actual Garmin API structure
            hrv_summary = data.get("hrvSummary", {})

            parsed_data = {}

            # Primary HRV value - use lastNightAvg as RMSSD equivalent
            if (
                "lastNightAvg" in hrv_summary
                and hrv_summary["lastNightAvg"] is not None
            ):
                parsed_data["hrv_rmssd"] = float(hrv_summary["lastNightAvg"])

            # Weekly average as backup SDRR value
            if "weeklyAvg" in hrv_summary and hrv_summary["weeklyAvg"] is not None:
                parsed_data["hrv_sdrr"] = float(hrv_summary["weeklyAvg"])

            # No direct score in Garmin API, use lastNightAvg
            if (
                "lastNightAvg" in hrv_summary
                and hrv_summary["lastNightAvg"] is not None
            ):
                parsed_data["hrv_score"] = float(hrv_summary["lastNightAvg"])

            if not any(parsed_data.values()):
                return None

            return cls(**parsed_data)

        except Exception as e:
            print(f"Warning: Could not parse HRV data: {e}")
            return None


class GarminStressData(BaseModel):
    """Pydantic model for Garmin stress data."""

    avg_stress: float | None = Field(None, description="Average stress level")
    max_stress: float | None = Field(None, description="Maximum stress level")
    stress_score: float | None = Field(None, description="Stress score")

    @classmethod
    def from_garmin_response(cls, data: dict[str, Any]) -> Optional["GarminStressData"]:
        """Create from Garmin API response."""
        if not data:
            return None

        try:
            parsed_data = {}

            # Use the actual Garmin API field names - handle None values
            if "avgStressLevel" in data and data["avgStressLevel"] is not None:
                parsed_data["avg_stress"] = float(data["avgStressLevel"])

            if "maxStressLevel" in data and data["maxStressLevel"] is not None:
                parsed_data["max_stress"] = float(data["maxStressLevel"])

            # Use average as score since no direct score available
            if "avgStressLevel" in data and data["avgStressLevel"] is not None:
                parsed_data["stress_score"] = float(data["avgStressLevel"])

            if not any(parsed_data.values()):
                return None

            return cls(**parsed_data)

        except Exception as e:
            print(f"Warning: Could not parse stress data: {e}")
            return None


class GarminHeartRateData(BaseModel):
    """Pydantic model for Garmin heart rate data."""

    resting_hr: int | None = Field(None, description="Resting heart rate")
    max_hr: int | None = Field(None, description="Maximum heart rate")
    avg_hr: int | None = Field(None, description="Average heart rate")

    @field_validator("resting_hr", "max_hr", "avg_hr", mode="before")
    @classmethod
    def validate_heart_rate(cls, v):
        """Validate heart rate values are reasonable."""
        if v is None:
            return None
        try:
            hr = int(float(v))
            # Reasonable heart rate range
            if 30 <= hr <= 220:
                return hr
            return None
        except (ValueError, TypeError):
            return None

    @classmethod
    def from_garmin_response(
        cls, data: dict[str, Any]
    ) -> Optional["GarminHeartRateData"]:
        """Create from Garmin API response."""
        if not data:
            return None

        try:
            field_mappings = {
                "resting_hr": ["restingHeartRate", "resting_hr", "restingHR", "rhr"],
                "max_hr": ["maxHeartRate", "max_hr", "maxHR", "maximumHR"],
                "avg_hr": [
                    "avgHeartRate",
                    "averageHeartRate",
                    "avg_hr",
                    "averageHR",
                    "avgHR",
                    "minHeartRate",
                ],
            }

            parsed_data = {}
            for field, possible_keys in field_mappings.items():
                for key in possible_keys:
                    if key in data and data[key] is not None:
                        parsed_data[field] = data[key]
                        break

            if not any(parsed_data.values()):
                return None

            return cls(**parsed_data)

        except Exception as e:
            print(f"Warning: Could not parse heart rate data: {e}")
            return None


class GarminWeightData(BaseModel):
    """Pydantic model for Garmin weight data."""

    weight: float | None = Field(None, description="Weight in kg")
    bmi: float | None = Field(None, description="Body Mass Index")
    body_fat: float | None = Field(None, description="Body fat percentage")
    muscle_mass: float | None = Field(None, description="Muscle mass in kg")

    @field_validator("weight", "bmi", "body_fat", "muscle_mass", mode="before")
    @classmethod
    def validate_weight_metrics(cls, v):
        """Validate weight metrics are reasonable."""
        if v is None:
            return None
        try:
            value = float(v)
            if value > 0:
                return value
            return None
        except (ValueError, TypeError):
            return None

    @classmethod
    def from_garmin_response(cls, data: dict[str, Any]) -> Optional["GarminWeightData"]:
        """Create from Garmin API response."""
        if not data:
            return None

        try:
            field_mappings = {
                "weight": ["weight", "bodyWeight", "weightKg"],
                "bmi": ["bmi", "bodyMassIndex", "BMI"],
                "body_fat": ["bodyFat", "body_fat", "fatPercentage"],
                "muscle_mass": ["muscleMass", "muscle_mass", "muscleKg"],
            }

            parsed_data = {}
            for field, possible_keys in field_mappings.items():
                for key in possible_keys:
                    if key in data and data[key] is not None:
                        parsed_data[field] = data[key]
                        break

            if not any(parsed_data.values()):
                return None

            return cls(**parsed_data)

        except Exception as e:
            print(f"Warning: Could not parse weight data: {e}")
            return None


class GarminStepsData(BaseModel):
    """Pydantic model for Garmin steps data."""

    total_steps: int | None = Field(None, description="Total steps for the day")
    total_distance: float | None = Field(None, description="Total distance in meters")
    step_goal: int | None = Field(None, description="Daily step goal")

    @field_validator("total_steps", "step_goal", mode="before")
    @classmethod
    def validate_steps(cls, v):
        """Validate step counts are reasonable."""
        if v is None:
            return None
        try:
            steps = int(v)
            if steps >= 0:
                return steps
            return None
        except (ValueError, TypeError):
            return None

    @field_validator("total_distance", mode="before")
    @classmethod
    def validate_distance(cls, v):
        """Validate distance is reasonable."""
        if v is None:
            return None
        try:
            distance = float(v)
            if distance >= 0:
                return distance
            return None
        except (ValueError, TypeError):
            return None

    @classmethod
    def from_garmin_response(cls, data: dict[str, Any]) -> Optional["GarminStepsData"]:
        """Create from Garmin API response."""
        if not data:
            return None

        try:
            parsed_data = {}

            # Use the actual Garmin API field names
            if "totalSteps" in data:
                parsed_data["total_steps"] = data["totalSteps"]

            if "totalDistance" in data:
                parsed_data["total_distance"] = data["totalDistance"]

            if "stepGoal" in data:
                parsed_data["step_goal"] = data["stepGoal"]

            if not any(parsed_data.values()):
                return None

            return cls(**parsed_data)

        except Exception as e:
            print(f"Warning: Could not parse steps data: {e}")
            return None
