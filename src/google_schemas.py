import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from logging_config import get_logger

logger = get_logger(__name__)


class GoogleDailyData(BaseModel):
    date: datetime.date = Field(..., description="Date of the record")
    total_steps: int | None = Field(None, description="Total steps for the day")
    total_distance: float | None = Field(None, description="Total distance in meters")
    total_calories: float | None = Field(None, description="Total calories burned")
    move_minutes: int | None = Field(None, description="Active minutes")
    heart_points: float | None = Field(None, description="Heart points earned")
    avg_heart_rate: int | None = Field(None, description="Average heart rate")
    max_heart_rate: int | None = Field(None, description="Max heart rate")
    min_heart_rate: int | None = Field(None, description="Min heart rate")
    avg_weight_kg: float | None = Field(None, description="Average weight in kg")
    walking_duration_ms: int | None = Field(None, description="Walking duration in ms")
    inactive_duration_ms: int | None = Field(
        None, description="Inactive duration in ms"
    )

    @field_validator("total_steps", mode="before")
    @classmethod
    def validate_steps(cls, v):
        if v is None or v == "":
            return None
        try:
            steps = int(float(v))
            return steps if steps >= 0 else None
        except (ValueError, TypeError):
            return None

    @field_validator("total_distance", "total_calories", mode="before")
    @classmethod
    def validate_float(cls, v):
        if v is None or v == "":
            return None
        try:
            val = float(v)
            return val if val >= 0 else None
        except (ValueError, TypeError):
            return None

    @field_validator("move_minutes", mode="before")
    @classmethod
    def validate_minutes(cls, v):
        if v is None or v == "":
            return None
        try:
            mins = int(float(v))
            return mins if mins >= 0 else None
        except (ValueError, TypeError):
            return None

    @field_validator("heart_points", mode="before")
    @classmethod
    def validate_heart_points(cls, v):
        if v is None or v == "":
            return None
        try:
            return float(v)
        except (ValueError, TypeError):
            return None

    @field_validator(
        "avg_heart_rate", "max_heart_rate", "min_heart_rate", mode="before"
    )
    @classmethod
    def validate_heart_rate(cls, v):
        if v is None or v == "":
            return None
        try:
            hr = int(float(v))
            if hr < 20 or hr > 250:
                return None
            return hr
        except (ValueError, TypeError):
            return None

    @field_validator("avg_weight_kg", mode="before")
    @classmethod
    def validate_weight(cls, v):
        if v is None or v == "":
            return None
        try:
            weight = float(v)
            if weight < 20 or weight > 300:
                return None
            return weight
        except (ValueError, TypeError):
            return None

    @field_validator("walking_duration_ms", "inactive_duration_ms", mode="before")
    @classmethod
    def validate_duration(cls, v):
        if v is None or v == "":
            return None
        try:
            return int(float(v))
        except (ValueError, TypeError):
            return None

    @classmethod
    def from_csv_aggregation(
        cls, date: datetime.date, rows: list[dict[str, Any]]
    ) -> "GoogleDailyData":
        total_steps = 0
        total_distance = 0.0
        total_calories = 0.0
        total_move_minutes = 0
        total_heart_points = 0.0
        heart_rates: list[int] = []
        weights: list[float] = []
        total_walking_ms = 0
        total_inactive_ms = 0

        for row in rows:
            if row.get("Step count"):
                try:
                    total_steps += int(float(row["Step count"]))
                except (ValueError, TypeError):
                    pass

            if row.get("Distance (m)"):
                try:
                    total_distance += float(row["Distance (m)"])
                except (ValueError, TypeError):
                    pass

            if row.get("Calories (kcal)"):
                try:
                    total_calories += float(row["Calories (kcal)"])
                except (ValueError, TypeError):
                    pass

            if row.get("Move Minutes count"):
                try:
                    total_move_minutes += int(float(row["Move Minutes count"]))
                except (ValueError, TypeError):
                    pass

            if row.get("Heart Points"):
                try:
                    total_heart_points += float(row["Heart Points"])
                except (ValueError, TypeError):
                    pass

            if row.get("Average heart rate (bpm)"):
                try:
                    hr = int(float(row["Average heart rate (bpm)"]))
                    if 20 <= hr <= 250:
                        heart_rates.append(hr)
                except (ValueError, TypeError):
                    pass

            if row.get("Average weight (kg)"):
                try:
                    w = float(row["Average weight (kg)"])
                    if 20 <= w <= 300:
                        weights.append(w)
                except (ValueError, TypeError):
                    pass

            if row.get("Walking duration (ms)"):
                try:
                    total_walking_ms += int(float(row["Walking duration (ms)"]))
                except (ValueError, TypeError):
                    pass

            if row.get("Inactive duration (ms)"):
                try:
                    total_inactive_ms += int(float(row["Inactive duration (ms)"]))
                except (ValueError, TypeError):
                    pass

        avg_hr = int(sum(heart_rates) / len(heart_rates)) if heart_rates else None
        max_hr = max(heart_rates) if heart_rates else None
        min_hr = min(heart_rates) if heart_rates else None
        avg_weight = sum(weights) / len(weights) if weights else None

        return cls(
            date=date,
            total_steps=total_steps if total_steps > 0 else None,
            total_distance=total_distance if total_distance > 0 else None,
            total_calories=total_calories if total_calories > 0 else None,
            move_minutes=total_move_minutes if total_move_minutes > 0 else None,
            heart_points=total_heart_points if total_heart_points > 0 else None,
            avg_heart_rate=avg_hr,
            max_heart_rate=max_hr,
            min_heart_rate=min_hr,
            avg_weight_kg=avg_weight,
            walking_duration_ms=total_walking_ms if total_walking_ms > 0 else None,
            inactive_duration_ms=total_inactive_ms if total_inactive_ms > 0 else None,
        )
