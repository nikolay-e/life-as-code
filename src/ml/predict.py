from datetime import date, timedelta

import numpy as np
import pandas as pd
import structlog
import torch
from chronos import BaseChronosPipeline, ChronosBoltPipeline
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ml.config import MLConfig
from models import Prediction

logger = structlog.get_logger()


BOLT_P10_IDX = 0
BOLT_P50_IDX = 4
BOLT_P90_IDX = 8


def _extract_quantiles(forecast: torch.Tensor, pipeline, horizon_idx: int):
    if isinstance(pipeline, ChronosBoltPipeline):
        quantiles = forecast.numpy()[0]
        p10 = float(quantiles[BOLT_P10_IDX, horizon_idx])
        p50 = float(quantiles[BOLT_P50_IDX, horizon_idx])
        p90 = float(quantiles[BOLT_P90_IDX, horizon_idx])
    else:
        samples = forecast.numpy()[0]
        p10 = float(np.percentile(samples[:, horizon_idx], 10))
        p50 = float(np.percentile(samples[:, horizon_idx], 50))
        p90 = float(np.percentile(samples[:, horizon_idx], 90))
    return p10, p50, p90


def generate_forecasts(
    pipeline: BaseChronosPipeline,
    series_by_metric: dict[str, pd.DataFrame],
    config: MLConfig,
    user_id: int,
    db: Session,
) -> int:
    total_predictions = 0
    today = date.today()

    for metric, df in series_by_metric.items():
        if len(df) < config.min_training_days:
            logger.warning(
                "insufficient_data",
                metric=metric,
                days=len(df),
                required=config.min_training_days,
            )
            continue

        context = torch.tensor(df["value"].values, dtype=torch.float32).unsqueeze(0)
        max_horizon = max(config.forecast_horizons)

        predict_kwargs = {"prediction_length": max_horizon}
        if not isinstance(pipeline, ChronosBoltPipeline):
            predict_kwargs["num_samples"] = 100

        forecast = pipeline.predict(context, **predict_kwargs)

        records = []
        forecast_len = forecast.shape[-1]

        for horizon in config.forecast_horizons:
            if horizon > forecast_len:
                continue

            p10, p50, p90 = _extract_quantiles(forecast, pipeline, horizon - 1)

            records.append(
                {
                    "user_id": user_id,
                    "metric": metric,
                    "target_date": today + timedelta(days=horizon),
                    "horizon_days": horizon,
                    "p10": round(p10, 2),
                    "p50": round(p50, 2),
                    "p90": round(p90, 2),
                    "model_version": config.chronos_base_model,
                }
            )

        if records:
            stmt = insert(Prediction).values(records)
            stmt = stmt.on_conflict_do_update(
                index_elements=["user_id", "metric", "target_date", "horizon_days"],
                set_={
                    "p10": stmt.excluded.p10,
                    "p50": stmt.excluded.p50,
                    "p90": stmt.excluded.p90,
                    "model_version": stmt.excluded.model_version,
                },
            )
            db.execute(stmt)
            total_predictions += len(records)
            logger.info("forecast_generated", metric=metric, predictions=len(records))

    db.commit()
    return total_predictions
