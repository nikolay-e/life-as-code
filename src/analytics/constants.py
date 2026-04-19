from .types import TrendMode, TrendModeConfig

STEP_GOAL_DEFAULT = 10000
STEP_FLOOR_FALLBACK = 4000
WHOOP_MAX_STRAIN = 21

MIN_SAMPLE_SIZE = 14
MIN_CORRELATION_PAIRS = 7
MIN_LAG_SAMPLE_SIZE = 30
MIN_STD_THRESHOLD = 1e-6
MAD_SCALE_FACTOR = 1.4826
CONFIDENCE_THRESHOLD = 0.6

TREND_MODES: dict[TrendMode, TrendModeConfig] = {
    TrendMode.RECENT: TrendModeConfig(
        range_days=42,
        short_term=7,
        long_term=14,
        baseline=42,
        trend_window=7,
        use_shifted_z_score=False,
    ),
    TrendMode.QUARTER: TrendModeConfig(
        range_days=180,
        short_term=14,
        long_term=30,
        baseline=90,
        trend_window=14,
        use_shifted_z_score=True,
    ),
    TrendMode.YEAR: TrendModeConfig(
        range_days=730,
        short_term=30,
        long_term=90,
        baseline=180,
        trend_window=30,
        use_shifted_z_score=True,
    ),
    TrendMode.ALL: TrendModeConfig(
        range_days=1825,
        short_term=90,
        long_term=180,
        baseline=365,
        trend_window=60,
        use_shifted_z_score=True,
    ),
}

MAX_BASELINE_DAYS = max(cfg.baseline for cfg in TREND_MODES.values())

METRIC_AGGREGATION: dict[str, str] = {
    "hrv": "mean",
    "rhr": "mean",
    "sleep": "last",
    "stress": "mean",
    "steps": "last",
    "strain": "max",
    "calories": "last",
    "weight": "last",
    "recovery": "last",
    "respiratory_rate": "mean",
    "sleep_deep": "last",
    "sleep_rem": "last",
    "sleep_score": "last",
    "bed_temp": "last",
    "room_temp": "last",
}

METRIC_COMPLETENESS_THRESHOLDS: dict[str, float] = {
    "steps": 0.8,
    "calories": 0.85,
    "strain": 0.85,
    "stress": 0.9,
}

INSTANTANEOUS_METRICS = {"hrv", "rhr", "sleep", "recovery", "weight"}

PHYSIOLOGICAL_LIMITS: dict[str, dict[str, float]] = {
    "hrv": {"min": 5, "max": 300, "typical_min": 15, "typical_max": 150},
    "sleep": {"min": 0, "max": 840, "typical_min": 240, "typical_max": 660},
    "resting_hr": {"min": 30, "max": 120, "typical_min": 40, "typical_max": 90},
    "strain": {"min": 0, "max": 21, "typical_min": 0, "typical_max": 21},
    "calories": {"min": 500, "max": 10000, "typical_min": 1500, "typical_max": 4000},
    "respiratory_rate": {"min": 5, "max": 40, "typical_min": 10, "typical_max": 25},
    "sleep_deep": {"min": 0, "max": 300, "typical_min": 30, "typical_max": 180},
    "sleep_rem": {"min": 0, "max": 300, "typical_min": 30, "typical_max": 180},
}

MIN_OVERLAP_FOR_BLENDING = 7
MIN_OVERLAP_FOR_NORMALIZATION = 14
SOURCE_STATS_WINDOW = 30

TACHYCARDIA_SIGMA = 2
TACHYCARDIA_MIN_DAYS = 3
HRV_DROP_THRESHOLD = 0.3
WEIGHT_LOSS_THRESHOLD = 0.05
ACWR_DANGER_THRESHOLD = 1.5
HRV_LOW_SIGMA = -1.5

OVERREACHING_THRESHOLDS = {"low": 0.33, "moderate": 0.55, "high": 0.75}

ANOMALY_THRESHOLDS = {"warning": 2.0, "alert": 2.5, "critical": 3.0}

VELOCITY_SIGNIFICANCE = {
    "hrv": 0.5,
    "rhr": 0.3,
    "weight": 0.02,
    "sleep": 5.0,
}

HIGH_STRAIN_Z_THRESHOLD = 1.5
RECOVERY_LOOKBACK_DAYS = 7
RECOVERED_Z_THRESHOLD = 0.0

ILLNESS_RISK_THRESHOLDS = {"moderate": 3.0, "high": 5.0}
ELEVATED_DAY_THRESHOLD = 1.5

DECORRELATION_BASELINE_MIN = -0.3
DECORRELATION_CURRENT_MAX = -0.15

CALORIES_TREND_THRESHOLD = 100
WEIGHT_TREND_THRESHOLD = 0.2
SLEEP_OPTIMAL_HOURS = 7.5
SLEEP_OVERSLEEP_HOURS = 9.0
SLEEP_QUADRATIC_FACTOR = 4.5

WEIGHT_MIN_BASELINE = 180
MAX_SLEEP_TARGET_WINDOW = 90
MAX_STEPS_FLOOR_WINDOW = 90
MIN_STEPS_FLOOR_DATA = 14
STEPS_FLOOR_PERCENTILE = 10

SCORE_QUALITY_WINDOW = 30

HEALTH_SCORE_CORE_WEIGHTS = {"hrv": 0.35, "rhr": 0.25, "sleep": 0.25, "stress": 0.15}
HEALTH_SCORE_SUPPORT_WEIGHTS = {"steps": 0.35, "calories": 0.35, "weight": 0.30}

OVERALL_RECOVERY_WEIGHT_WITHOUT_TRAINING = 0.75
OVERALL_RECOVERY_WEIGHT_WITH_TRAINING = 0.6
OVERALL_TRAINING_LOAD_WEIGHT = 0.2
OVERALL_SUPPORT_WEIGHT_WITHOUT_TRAINING = 0.25
OVERALL_SUPPORT_WEIGHT_WITH_TRAINING = 0.2

Z_SCORE_CLAMP = 3.0
STRAIN_OPTIMAL_Z = 0.3
STRAIN_GOODNESS_INNER_RADIUS = 0.5
STRAIN_GOODNESS_MAX_BONUS = 0.3
STRAIN_GOODNESS_PENALTY_RATE = 0.3

CALORIES_GOODNESS_EXCESS_PENALTY_RATE = 0.3
CALORIES_GOODNESS_EXCESS_DEAD_ZONE = 0.5
CALORIES_GOODNESS_DEFICIT_RATE = 0.4

WEIGHT_GOODNESS_GAIN_PENALTY_RATE = 0.6
WEIGHT_GOODNESS_LOSS_PENALTY_RATE = 0.3

STEPS_RECOVERY_CAP_HRV_THRESHOLDS = (-0.5, -1.0, -1.5)
STEPS_RECOVERY_CAP_MULTIPLIERS = (0.7, 0.4, 0.2)

CONFIDENCE_GATE_THRESHOLD = 0.6
CONFIDENCE_GATE_WIDTH = 0.15
CONFIDENCE_GATE_STEEPNESS = 5

DATA_QUALITY_COVERAGE_WEIGHT = 0.7
DATA_QUALITY_SUFFICIENCY_WEIGHT = 0.3

STEPS_TODAY_MIN_MULTIPLIER = 0.15

TREND_MIN_DATA_FACTOR = 0.7
TREND_MIN_DATA_CAP = 14
TREND_MIN_DATA_FLOOR = 3

CALORIES_FALLBACK_CONFIDENCE = 0.7
WEIGHT_FALLBACK_CONFIDENCE = 0.8

TRAINING_LOAD_GATE_THRESHOLD = 0.1
MIN_CORE_METRICS = 2

HRV_AGE_DECAY_RATE = 0.03
HRV_AGE_BASELINE_HRV = 80.0
HRV_AGE_BASELINE_AGE = 20

RHR_REFERENCE = 60

VO2MAX_NORMATIVE_MALE: dict[int, dict[str, float]] = {
    20: {"p90": 55.0, "p50": 43.0, "p10": 33.0},
    30: {"p90": 52.0, "p50": 40.0, "p10": 30.0},
    40: {"p90": 48.0, "p50": 36.0, "p10": 27.0},
    50: {"p90": 44.0, "p50": 33.0, "p10": 24.0},
    60: {"p90": 39.0, "p50": 29.0, "p10": 21.0},
    70: {"p90": 35.0, "p50": 25.0, "p10": 18.0},
}

LONGEVITY_SCORE_WEIGHTS = {
    "cardiorespiratory": 0.30,
    "recovery_resilience": 0.25,
    "sleep_optimization": 0.20,
    "body_composition": 0.15,
    "activity_consistency": 0.10,
}

ZONE2_WEEKLY_TARGET_MINUTES = 150
ZONE5_WEEKLY_TARGET_MINUTES = 4

MIN_BIO_AGE_DATA_DAYS = 14

BIO_AGE_METRIC_RELIABILITY = {
    "hrv_age": 0.85,
    "fitness_age": 0.90,
    "fitness_age_native": 0.75,
    "rhr_age": 0.60,
    "recovery_age": 0.50,
}
