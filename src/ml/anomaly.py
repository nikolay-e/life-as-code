import pandas as pd
import structlog
from scipy.stats import rankdata
from sklearn.ensemble import IsolationForest
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ml.config import MLConfig
from models import Anomaly

logger = structlog.get_logger()


def detect_anomalies(
    model: IsolationForest,
    features_df: pd.DataFrame,
    config: MLConfig,
    user_id: int,
    db: Session,
) -> int:
    if features_df.empty:
        return 0

    numeric_df = features_df.select_dtypes(include="number")
    scores_raw = model.decision_function(numeric_df)
    labels = model.predict(numeric_df)

    ranks = rankdata(scores_raw)
    scores = (1 - ranks / len(ranks)).tolist()

    means = numeric_df.mean()
    stds = numeric_df.std()
    z_scores = (numeric_df - means) / (stds + 1e-10)

    records = []
    for i, (idx, row) in enumerate(numeric_df.iterrows()):
        if labels[i] == -1:
            day_z = z_scores.loc[idx]
            top_factors = day_z.abs().nlargest(3)
            contributing = {
                col: {
                    "z_score": round(float(day_z[col]), 2),
                    "value": round(float(row[col]), 2),
                }
                for col in top_factors.index
            }

            records.append(
                {
                    "user_id": user_id,
                    "date": idx.date() if hasattr(idx, "date") else idx,
                    "anomaly_score": round(min(max(float(scores[i]), 0.0), 1.0), 3),
                    "contributing_factors": contributing,
                    "model_version": f"isolation_forest_n{config.anomaly_lookback_days}",
                }
            )

    if records:
        stmt = insert(Anomaly).values(records)
        stmt = stmt.on_conflict_do_update(
            index_elements=["user_id", "date"],
            set_={
                "anomaly_score": stmt.excluded.anomaly_score,
                "contributing_factors": stmt.excluded.contributing_factors,
                "model_version": stmt.excluded.model_version,
            },
        )
        db.execute(stmt)
        db.commit()
        logger.info("anomalies_detected", count=len(records))

    return len(records)
