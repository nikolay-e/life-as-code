from pathlib import Path
from typing import Any

import yaml

from logging_config import get_logger

logger = get_logger(__name__)


class ConfigLoader:
    """Singleton configuration loader."""

    _instance = None
    _config = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._config is None:
            self._config = {}
            self._load_config()

    def _load_config(self):
        """Load configuration from YAML files."""
        config_dir = Path(__file__).parent / "config"

        # Load thresholds
        thresholds_path = config_dir / "thresholds.yaml"
        if thresholds_path.exists():
            with open(thresholds_path) as f:
                self._config["thresholds"] = yaml.safe_load(f)
        else:
            # Fallback to hardcoded values if config file doesn't exist
            self._config["thresholds"] = self._get_default_thresholds()

    def _get_default_thresholds(self) -> dict[str, Any]:
        """Fallback default thresholds if YAML file is not found."""
        return {
            "hrv": {"good": 45, "moderate": 35},
            "sleep": {
                "deep_sleep": {"good": 90, "moderate": 60},
                "total_sleep": {"good": 7.5, "moderate": 6.5},
            },
            "training": {"high_volume": 5000},
            "stress": {"low": 25, "moderate": 50, "high": 75},
            "heart_rate": {"resting": {"excellent": 50, "good": 60, "fair": 70}},
            "activity": {
                "daily_steps": {"goal": 10000, "active": 8000, "sedentary": 5000}
            },
            "body_composition": {
                "body_fat": {
                    "male": {"excellent": 10, "good": 15, "fair": 20},
                    "female": {"excellent": 16, "good": 21, "fair": 26},
                }
            },
            "energy": {"active_calories": {"high": 600, "moderate": 300, "low": 150}},
        }

    def get_threshold(self, path: str, default: Any = None) -> Any:
        """
        Get a threshold value using dot notation.

        Examples:
            get_threshold('hrv.good') -> 45
            get_threshold('sleep.deep_sleep.good') -> 90
            get_threshold('nonexistent', 0) -> 0
        """
        keys = path.split(".")
        config: dict[str, Any] = self._config or {}
        value = config.get("thresholds", {})

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default

        return value

    def get_all_thresholds(self) -> dict[str, Any]:
        """Get all threshold configuration."""
        config: dict[str, Any] = self._config or {}
        thresholds: dict[str, Any] = config.get("thresholds", {})
        return thresholds

    def reload_config(self):
        """Reload configuration from files."""
        self._config = {}
        self._load_config()


# Global config instance
config = ConfigLoader()


def get_threshold(path: str, default: Any = None) -> Any:
    """Convenience function to get threshold values."""
    return config.get_threshold(path, default)


def get_user_thresholds(user_id: int) -> dict[str, Any]:
    """
    Get thresholds for a user, with database overrides if available.
    Falls back to config file defaults if no user-specific values exist.
    """
    try:
        from sqlalchemy import select

        from database import get_db_session_context
        from models import UserSettings

        with get_db_session_context() as db:
            user_settings = db.scalars(
                select(UserSettings).where(UserSettings.user_id == user_id)
            ).first()

            if user_settings:
                # Return user-specific thresholds
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

    # Return config file defaults
    return {
        "hrv_good": get_threshold("hrv.good", 45),
        "hrv_moderate": get_threshold("hrv.moderate", 35),
        "deep_sleep_good": get_threshold("sleep.deep_sleep.good", 90),
        "deep_sleep_moderate": get_threshold("sleep.deep_sleep.moderate", 60),
        "total_sleep_good": get_threshold("sleep.total_sleep.good", 7.5),
        "total_sleep_moderate": get_threshold("sleep.total_sleep.moderate", 6.5),
        "training_high_volume": get_threshold("training.high_volume", 5000),
    }
