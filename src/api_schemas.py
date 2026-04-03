from __future__ import annotations

import math
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class LoginRequest(BaseModel):
    username: str
    password: str


class GarminCredentialsRequest(BaseModel):
    email: str = Field(max_length=200)
    password: str = Field(max_length=256)

    @field_validator("email")
    @classmethod
    def strip_and_check_email(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("email is required")
        if "@" not in v:
            raise ValueError("invalid email format")
        return v

    @field_validator("password")
    @classmethod
    def strip_and_check_password(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("password is required")
        return v


class HevyCredentialsRequest(BaseModel):
    api_key: str = Field(max_length=256)

    @field_validator("api_key")
    @classmethod
    def strip_and_check(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("api_key is required")
        return v


class ThresholdSettings(BaseModel):
    hrv_good_threshold: int | None = Field(None, ge=0, le=500)
    hrv_moderate_threshold: int | None = Field(None, ge=0, le=500)
    deep_sleep_good_threshold: int | None = Field(None, ge=0, le=500)
    deep_sleep_moderate_threshold: int | None = Field(None, ge=0, le=500)
    total_sleep_good_threshold: float | None = Field(None, ge=0, le=24)
    total_sleep_moderate_threshold: float | None = Field(None, ge=0, le=24)
    training_high_volume_threshold: int | None = Field(None, ge=0, le=100000)


class ProfileUpdate(BaseModel):
    birth_date: date | None = None
    gender: Literal["male", "female"] | None = None


def _check_finite(v: float | None) -> float | None:
    if v is not None and not math.isfinite(v):
        raise ValueError("must be a finite number")
    return v


class BiomarkerCreate(BaseModel):
    date: date
    marker_name: str
    value: float
    unit: str
    reference_range_low: float | None = None
    reference_range_high: float | None = None
    longevity_optimal_low: float | None = None
    longevity_optimal_high: float | None = None
    lab_name: str | None = None
    notes: str | None = None

    @field_validator(
        "value",
        "reference_range_low",
        "reference_range_high",
        "longevity_optimal_low",
        "longevity_optimal_high",
    )
    @classmethod
    def validate_finite(cls, v: float | None) -> float | None:
        return _check_finite(v)


class InterventionCreate(BaseModel):
    name: str
    category: Literal["supplement", "protocol", "medication", "lifestyle", "diet"]
    start_date: date
    end_date: date | None = None
    dosage: str | None = None
    frequency: str | None = None
    target_metrics: Any = None
    notes: str | None = None


class InterventionUpdate(BaseModel):
    name: str | None = None
    category: (
        Literal["supplement", "protocol", "medication", "lifestyle", "diet"] | None
    ) = None
    end_date: date | None = None
    dosage: str | None = None
    frequency: str | None = None
    target_metrics: Any = None
    notes: str | None = None
    active: bool | None = None


class FunctionalTestCreate(BaseModel):
    date: date
    test_name: str
    value: float
    unit: str
    notes: str | None = None

    @field_validator("value")
    @classmethod
    def validate_finite(cls, v: float) -> float:
        if not math.isfinite(v):
            raise ValueError("must be a finite number")
        return v


class GoalCreate(BaseModel):
    category: str
    description: str
    target_value: float | None = None
    current_value: float | None = None
    unit: str | None = None
    target_age: int | None = None

    @field_validator("target_value", "current_value")
    @classmethod
    def validate_finite(cls, v: float | None) -> float | None:
        return _check_finite(v)


class GoalUpdate(BaseModel):
    category: str | None = None
    description: str | None = None
    target_value: float | None = None
    current_value: float | None = None
    unit: str | None = None
    target_age: int | None = None

    @field_validator("target_value", "current_value")
    @classmethod
    def validate_finite(cls, v: float | None) -> float | None:
        return _check_finite(v)
