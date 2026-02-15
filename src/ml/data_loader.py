from datetime import date, timedelta

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

METRIC_QUERIES = {
    "weight": "SELECT date, AVG(weight_kg) as value FROM weight WHERE user_id = :uid AND weight_kg IS NOT NULL GROUP BY date ORDER BY date",
    "hrv": "SELECT date, AVG(hrv_avg) as value FROM hrv WHERE user_id = :uid AND hrv_avg IS NOT NULL GROUP BY date ORDER BY date",
    "rhr": "SELECT date, AVG(resting_hr) as value FROM heart_rate WHERE user_id = :uid AND resting_hr IS NOT NULL GROUP BY date ORDER BY date",
    "sleep_total": "SELECT date, AVG(total_sleep_minutes) as value FROM sleep WHERE user_id = :uid AND total_sleep_minutes IS NOT NULL GROUP BY date ORDER BY date",
    "steps": "SELECT date, SUM(total_steps) as value FROM steps WHERE user_id = :uid AND total_steps IS NOT NULL GROUP BY date ORDER BY date",
}

ANOMALY_QUERY = """
SELECT
    s.date,
    COALESCE(AVG(st.total_steps), 0) as steps,
    COALESCE(AVG(sl.total_sleep_minutes), 0) as sleep_minutes,
    COALESCE(AVG(hr.resting_hr), 0) as resting_hr,
    COALESCE(AVG(h.hrv_avg), 0) as hrv,
    COALESCE(AVG(w.weight_kg), 0) as weight,
    COALESCE(AVG(e.active_energy), 0) as active_energy,
    COALESCE(AVG(str.avg_stress), 0) as avg_stress
FROM (
    SELECT DISTINCT date FROM steps WHERE user_id = :uid AND date >= :start_date
    UNION SELECT DISTINCT date FROM sleep WHERE user_id = :uid AND date >= :start_date
    UNION SELECT DISTINCT date FROM heart_rate WHERE user_id = :uid AND date >= :start_date
) s
LEFT JOIN steps st ON st.date = s.date AND st.user_id = :uid
LEFT JOIN sleep sl ON sl.date = s.date AND sl.user_id = :uid
LEFT JOIN heart_rate hr ON hr.date = s.date AND hr.user_id = :uid
LEFT JOIN hrv h ON h.date = s.date AND h.user_id = :uid
LEFT JOIN weight w ON w.date = s.date AND w.user_id = :uid
LEFT JOIN energy e ON e.date = s.date AND e.user_id = :uid
LEFT JOIN stress str ON str.date = s.date AND str.user_id = :uid
GROUP BY s.date
ORDER BY s.date
"""


def load_metric_series(db: Session, user_id: int, metric: str) -> pd.DataFrame:
    query = METRIC_QUERIES.get(metric)
    if not query:
        raise ValueError(f"Unknown metric: {metric}")

    result = db.execute(text(query), {"uid": user_id})
    rows = result.fetchall()

    if not rows:
        return pd.DataFrame(columns=["date", "value"])

    df = pd.DataFrame(rows, columns=["date", "value"])
    df["date"] = pd.to_datetime(df["date"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.set_index("date").asfreq("D")
    df["value"] = df["value"].interpolate(method="linear", limit=3)
    return df.dropna()


def load_anomaly_features(
    db: Session, user_id: int, lookback_days: int = 90
) -> pd.DataFrame:
    start_date = date.today() - timedelta(days=lookback_days)
    result = db.execute(text(ANOMALY_QUERY), {"uid": user_id, "start_date": start_date})
    rows = result.fetchall()

    if not rows:
        return pd.DataFrame()

    columns = [
        "date",
        "steps",
        "sleep_minutes",
        "resting_hr",
        "hrv",
        "weight",
        "active_energy",
        "avg_stress",
    ]
    df = pd.DataFrame(rows, columns=columns)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()

    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    numeric_cols = df.select_dtypes(include="number").columns
    df[numeric_cols] = df[numeric_cols].replace(0, pd.NA)
    df[numeric_cols] = df[numeric_cols].interpolate(method="linear", limit=3)

    return df.dropna()
