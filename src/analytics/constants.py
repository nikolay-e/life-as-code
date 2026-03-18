from .types import TrendMode, TrendModeConfig

STEP_GOAL_DEFAULT = 10000
STEP_FLOOR_FALLBACK = 4000
WHOOP_MAX_STRAIN = 21

MIN_SAMPLE_SIZE = 10
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
}

METRIC_COMPLETENESS_THRESHOLDS: dict[str, float] = {
    "steps": 0.8,
    "calories": 0.85,
    "strain": 0.85,
    "stress": 0.9,
}

PHYSIOLOGICAL_LIMITS: dict[str, dict[str, float]] = {
    "hrv": {"min": 5, "max": 300, "typical_min": 15, "typical_max": 150},
    "sleep": {"min": 0, "max": 840, "typical_min": 240, "typical_max": 660},
    "resting_hr": {"min": 30, "max": 120, "typical_min": 40, "typical_max": 90},
    "strain": {"min": 0, "max": 21, "typical_min": 0, "typical_max": 21},
    "calories": {"min": 500, "max": 10000, "typical_min": 1500, "typical_max": 4000},
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

MAX_SLEEP_TARGET_WINDOW = 90
MAX_STEPS_FLOOR_WINDOW = 90
MIN_STEPS_FLOOR_DATA = 14
STEPS_FLOOR_PERCENTILE = 10

SCORE_QUALITY_WINDOW = 30

HRV_AGE_DECAY_RATE = 0.03
HRV_AGE_BASELINE_HRV = 80.0
HRV_AGE_BASELINE_AGE = 20

RHR_REFERENCE = 60
RHR_HAZARD_PER_10BPM = 1.09

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
PACE_OF_AGING_LOOKBACK_DAYS = 365
