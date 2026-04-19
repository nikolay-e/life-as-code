import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

RESEARCH_ROOT = Path(__file__).parent.parent
SNAPSHOTS_DIR = RESEARCH_ROOT / "snapshots"

DEFAULT_DB_URL = os.environ.get(
    "LAC_DATABASE_URL",
    "postgresql://lifeascode_production:@localhost:5433/lifeascode_production",
)

DEFAULT_USER_ID = 1
DEFAULT_KEEP_LAST = 5

HEALTH_TABLES: dict[str, str] = {
    "sleep": "sleep",
    "hrv": "hrv",
    "weight": "weight",
    "heart_rate": "heart_rate",
    "stress": "stress",
    "energy": "energy",
    "steps": "steps",
    "workout_sets": "workout_sets",
    "whoop_recovery": "whoop_recovery",
    "whoop_sleep": "whoop_sleep",
    "whoop_workouts": "whoop_workouts",
    "whoop_cycles": "whoop_cycles",
    "garmin_training_status": "garmin_training_status",
    "garmin_activities": "garmin_activities",
    "garmin_race_predictions": "garmin_race_predictions",
    "eight_sleep_sessions": "eight_sleep_sessions",
    "blood_biomarkers": "blood_biomarkers",
    "interventions": "interventions",
    "functional_tests": "functional_tests",
    "longevity_goals": "longevity_goals",
}

# ML output tables: exported with _prod_ prefix for validation
PROD_TABLES: dict[str, str] = {
    "predictions": "predictions",
    "anomalies": "anomalies",
}


# MIRROR OF src/ml/config.py:detect_device — keep in sync
def detect_device() -> str:
    env_device = os.environ.get("DEVICE")
    if env_device:
        return env_device
    try:
        import torch

        if torch.cuda.is_available():
            return "cuda"
        if torch.backends.mps.is_available():
            return "mps"
    except ImportError:
        pass
    return "cpu"
