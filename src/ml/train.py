from pathlib import Path

import joblib
import structlog
import torch
from chronos import BaseChronosPipeline
from sklearn.ensemble import IsolationForest

from ml.config import MLConfig

logger = structlog.get_logger()


def load_chronos(config: MLConfig) -> BaseChronosPipeline:
    pipeline = BaseChronosPipeline.from_pretrained(
        config.chronos_base_model,
        device_map="cpu",
        torch_dtype=torch.float32,
    )
    logger.info("chronos_model_loaded", model=config.chronos_base_model)
    return pipeline


def save_chronos(pipeline: BaseChronosPipeline, path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    pipeline.inner_model.save_pretrained(path)
    logger.info("chronos_saved", path=str(path))


def load_chronos_from_disk(path: Path) -> BaseChronosPipeline:
    pipeline = BaseChronosPipeline.from_pretrained(
        str(path),
        device_map="cpu",
        torch_dtype=torch.float32,
    )
    logger.info("chronos_loaded_from_disk", path=str(path))
    return pipeline


def train_isolation_forest(features_df, config: MLConfig) -> IsolationForest:
    model = IsolationForest(
        contamination=config.anomaly_contamination,
        random_state=42,
        n_estimators=200,
        max_samples="auto",
    )
    numeric_df = features_df.select_dtypes(include="number")
    model.fit(numeric_df)
    logger.info("isolation_forest_trained", samples=len(numeric_df))
    return model


def save_iforest(model: IsolationForest, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, path)
    logger.info("iforest_saved", path=str(path))


def load_iforest(path: Path) -> IsolationForest:
    return joblib.load(path)
