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
