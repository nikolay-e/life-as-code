import argparse

import structlog

from database import get_db_session_context
from ml.anomaly import detect_anomalies
from ml.config import MLConfig
from ml.data_loader import load_anomaly_features, load_metric_series
from ml.predict import generate_forecasts
from ml.train import (
    load_chronos,
    load_chronos_from_disk,
    load_iforest,
    save_chronos,
    save_iforest,
    train_isolation_forest,
)

logger = structlog.get_logger()


def run_pipeline(user_id: int, do_train: bool = False) -> None:
    config = MLConfig()
    config.model_dir.mkdir(parents=True, exist_ok=True)

    chronos_path = config.model_dir / "chronos"
    iforest_path = config.model_dir / "isolation_forest.joblib"

    with get_db_session_context() as db:
        series_by_metric = {}
        for metric in config.metrics:
            df = load_metric_series(db, user_id, metric)
            if not df.empty:
                series_by_metric[metric] = df
                logger.info("data_loaded", metric=metric, days=len(df))

        if not series_by_metric:
            logger.error("no_data_available", user_id=user_id)
            return

        if do_train or not (chronos_path.exists() and any(chronos_path.iterdir())):
            chronos_pipeline = load_chronos(config)
            save_chronos(chronos_pipeline, chronos_path)
        else:
            chronos_pipeline = load_chronos_from_disk(chronos_path, config)

        n_forecasts = generate_forecasts(
            chronos_pipeline,
            series_by_metric,
            config,
            user_id,
            db,
        )
        logger.info("forecasts_complete", total=n_forecasts)

        anomaly_df = load_anomaly_features(db, user_id, config.anomaly_lookback_days)

        if anomaly_df.empty:
            logger.warning("no_anomaly_data", user_id=user_id)
            return

        if do_train or not iforest_path.exists():
            iforest = train_isolation_forest(anomaly_df, config)
            save_iforest(iforest, iforest_path)
        else:
            iforest = load_iforest(iforest_path)

        n_anomalies = detect_anomalies(iforest, anomaly_df, config, user_id, db)
        logger.info("anomaly_detection_complete", total=n_anomalies)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-id", type=int, required=True)
    parser.add_argument("--train", action="store_true")
    args = parser.parse_args()

    run_pipeline(args.user_id, args.train)


if __name__ == "__main__":
    main()
