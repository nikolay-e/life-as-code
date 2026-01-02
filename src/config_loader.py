from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from logging_config import get_logger

logger = get_logger(__name__)

_DEFAULT_THRESHOLDS: dict[str, Any] = {
    "hrv": {"good": 45, "moderate": 35},
    "sleep": {
        "deep_sleep": {"good": 90, "moderate": 60},
        "total_sleep": {"good": 7.5, "moderate": 6.5},
    },
    "training": {"high_volume": 5000},
    "stress": {"low": 25, "moderate": 50, "high": 75},
    "heart_rate": {"resting": {"excellent": 50, "good": 60, "fair": 70}},
    "activity": {"daily_steps": {"goal": 10000, "active": 8000, "sedentary": 5000}},
    "body_composition": {
        "body_fat": {
            "male": {"excellent": 10, "good": 15, "fair": 20},
            "female": {"excellent": 16, "good": 21, "fair": 26},
        }
    },
    "energy": {"active_calories": {"high": 600, "moderate": 300, "low": 150}},
}


@lru_cache(maxsize=1)
def _load_thresholds() -> dict[str, Any]:
    config_path = Path(__file__).parent / "config" / "thresholds.yaml"
    if config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f) or _DEFAULT_THRESHOLDS
    return _DEFAULT_THRESHOLDS


def get_threshold(path: str, default: Any = None) -> Any:
    keys = path.split(".")
    value: Any = _load_thresholds()
    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return default
    return value


def get_all_thresholds() -> dict[str, Any]:
    return _load_thresholds()


def get_user_thresholds(user_id: int) -> dict[str, Any]:
    try:
        from sqlalchemy import select

        from database import get_db_session_context
        from models import UserSettings

        with get_db_session_context() as db:
            user_settings = db.scalars(
                select(UserSettings).where(UserSettings.user_id == user_id)
            ).first()

            if user_settings:
                return {
                    "hrv_good": user_settings.hrv_good_threshold,
                    "hrv_moderate": user_settings.hrv_moderate_threshold,
                    "deep_sleep_good": user_settings.deep_sleep_good_threshold,
                    "deep_sleep_moderate": user_settings.deep_sleep_moderate_threshold,
                    "total_sleep_good": user_settings.total_sleep_good_threshold,
                    "total_sleep_moderate": user_settings.total_sleep_moderate_threshold,
                    "training_high_volume": user_settings.training_high_volume_threshold,
                }
    except Exception as e:
        logger.warning(
            "user_thresholds_db_query_failed",
            user_id=user_id,
            error_type=type(e).__name__,
            error=str(e),
        )

    return {
        "hrv_good": get_threshold("hrv.good", 45),
        "hrv_moderate": get_threshold("hrv.moderate", 35),
        "deep_sleep_good": get_threshold("sleep.deep_sleep.good", 90),
        "deep_sleep_moderate": get_threshold("sleep.deep_sleep.moderate", 60),
        "total_sleep_good": get_threshold("sleep.total_sleep.good", 7.5),
        "total_sleep_moderate": get_threshold("sleep.total_sleep.moderate", 6.5),
        "training_high_volume": get_threshold("training.high_volume", 5000),
    }
