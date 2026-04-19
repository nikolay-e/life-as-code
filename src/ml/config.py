import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class MLConfig:
    model_dir: Path = Path("/app/models")
    chronos_base_model: str = "amazon/chronos-bolt-base"
    device: str = field(default_factory=lambda: os.environ.get("DEVICE", "cpu"))
    forecast_horizons: list[int] = field(default_factory=lambda: [1, 7, 14])
    metrics: list[str] = field(
        default_factory=lambda: [
            "weight",
            "hrv",
            "rhr",
            "sleep_total",
            "steps",
            "respiratory_rate",
            "bed_temp",
            "sleep_score",
        ]
    )
    min_training_days: int = 30
    anomaly_contamination: float = 0.05
    anomaly_lookback_days: int = 90
    retrain_interval_days: int = 30
