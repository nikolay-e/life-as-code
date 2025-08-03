"""
Central configuration loader for Life-as-Code project.
Loads config.yaml and provides easy access to all configuration values.
"""

from pathlib import Path

import yaml


def load_config():
    """Load configuration from config.yaml file."""
    config_path = Path(__file__).parent / "config.yaml"

    if not config_path.exists():
        raise FileNotFoundError(
            f"Configuration file not found at {config_path}. "
            "Please create config.yaml from the template."
        )

    with open(config_path) as f:
        return yaml.safe_load(f)


# Load config once when module is imported
CONFIG = load_config()


# Convenience accessors for commonly used values
def get_recovery_thresholds():
    """Get recovery analysis thresholds."""
    return CONFIG["thresholds"]["recovery"]


def get_validation_ranges():
    """Get input validation ranges."""
    return CONFIG["validation"]


# Target values used across multiple scripts

# Recovery thresholds
HRV_THRESHOLDS = CONFIG["thresholds"]["recovery"]["hrv"]
SLEEP_THRESHOLDS = CONFIG["thresholds"]["recovery"]["deep_sleep_min"]
TOTAL_SLEEP_THRESHOLDS = CONFIG["thresholds"]["recovery"]["total_sleep_hours"]

# Training thresholds
TRAINING_THRESHOLDS = CONFIG["thresholds"]["training"]

# Validation ranges
BASIC_RANGES = CONFIG["validation"]["basic_ranges"]
