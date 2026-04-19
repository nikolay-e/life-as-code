# ---
# jupyter:
#   jupytext:
#     formats: py:percent
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.16.6
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
# ---

# %% [markdown]
# # Anomaly Detection Tuning
# Tune IsolationForest parameters and visualize anomaly scores.

# %%
import polars as pl
import plotly.express as px
import plotly.graph_objects as go

from src.loader import db, load

conn = db()

# %% [markdown]
# ## Build Feature Matrix

# %%
features = conn.sql(
    """
    WITH daily AS (
        SELECT DISTINCT date FROM sleep
        UNION SELECT DISTINCT date FROM hrv
        UNION SELECT DISTINCT date FROM heart_rate
    )
    SELECT
        d.date,
        COALESCE(step.total_steps, 0) as steps,
        COALESCE(s.total_sleep_minutes, 0) as sleep_minutes,
        hr.resting_hr,
        h.hrv_avg as hrv,
        w.weight_kg as weight,
        COALESCE(e.active_energy, 0) as active_energy,
        COALESCE(st.avg_stress, 0) as avg_stress
    FROM daily d
    LEFT JOIN sleep s ON d.date = s.date
    LEFT JOIN hrv h ON d.date = h.date
    LEFT JOIN heart_rate hr ON d.date = hr.date
    LEFT JOIN steps step ON d.date = step.date
    LEFT JOIN weight w ON d.date = w.date
    LEFT JOIN energy e ON d.date = e.date
    LEFT JOIN stress st ON d.date = st.date
    ORDER BY d.date
    """
).pl()

print(
    f"Feature matrix: {features.shape[0]} days "
    f"x {features.shape[1]} cols"
)
features.tail()

# %% [markdown]
# ## Train Isolation Forest with Different Contamination Levels

# %%
import numpy as np
from scipy.stats import rankdata
from sklearn.ensemble import IsolationForest

feature_cols = [c for c in features.columns if c != "date"]
X = features.select(feature_cols).to_pandas().fillna(0).values
dates = features["date"].to_list()

contamination_levels = [0.01, 0.03, 0.05, 0.07, 0.10]
results = {}

for cont in contamination_levels:
    model = IsolationForest(
        n_estimators=200, contamination=cont, random_state=42
    )
    model.fit(X)
    raw_scores = -model.decision_function(X)
    scores = rankdata(raw_scores) / len(raw_scores)
    n_anomalies = (scores > (1 - cont)).sum()
    results[cont] = {"scores": scores, "n_anomalies": n_anomalies}
    print(f"contamination={cont}: {n_anomalies} anomalies detected")

# %% [markdown]
# ## Anomaly Score Timeline

# %%
SELECTED_CONT = 0.05
scores = results[SELECTED_CONT]["scores"]
threshold = 1 - SELECTED_CONT

fig = go.Figure()
fig.add_trace(go.Scatter(
    x=dates,
    y=scores,
    mode="lines",
    name="Anomaly Score",
    line={"color": "steelblue"},
))
fig.add_hline(
    y=threshold,
    line_dash="dash",
    line_color="red",
    annotation_text=f"Threshold ({SELECTED_CONT})",
)
fig.update_layout(
    title=f"Anomaly Scores Over Time "
    f"(contamination={SELECTED_CONT})",
    xaxis_title="Date",
    yaxis_title="Anomaly Score (0-1)",
)
fig.show()

# %% [markdown]
# ## Anomalous Days: Contributing Factors

# %%
anomaly_mask = scores > threshold
anomaly_indices = np.nonzero(anomaly_mask)[0]

if len(anomaly_indices) > 0:
    mean_vals = X.mean(axis=0)
    std_vals = X.std(axis=0)
    std_vals[std_vals == 0] = 1

    contributing = []
    for idx in anomaly_indices:
        z_scores = (X[idx] - mean_vals) / std_vals
        top_3 = np.argsort(np.abs(z_scores))[-3:][::-1]
        factors = {
            feature_cols[i]: round(float(z_scores[i]), 2)
            for i in top_3
        }
        contributing.append({
            "date": dates[idx],
            "score": round(float(scores[idx]), 3),
            "top_factors": factors,
        })

    for entry in contributing[-10:]:
        print(
            f"{entry['date']}: score={entry['score']}, "
            f"factors={entry['top_factors']}"
        )

# %% [markdown]
# ## Compare with Production Anomalies

# %%
try:
    prod_anomalies = load("_prod_anomalies")
    if prod_anomalies.height > 0:
        print(
            f"Production anomalies: "
            f"{prod_anomalies.height} records"
        )
        print(prod_anomalies.sort("date").tail(10))

        local_dates = {
            str(dates[i]) for i in anomaly_indices
        }
        prod_dates = set(
            prod_anomalies["date"].cast(pl.Utf8).to_list()
        )
        overlap = local_dates & prod_dates
        print(
            f"\nOverlap: {len(overlap)} / "
            f"local={len(local_dates)}, "
            f"prod={len(prod_dates)}"
        )
    else:
        print("Production anomalies table is empty")
except FileNotFoundError:
    print(
        "No _prod_anomalies snapshot "
        "- run export with default tables"
    )

# %% [markdown]
# ## Sensitivity Analysis: Contamination vs Anomaly Count

# %%
fig = px.bar(
    x=[str(c) for c in contamination_levels],
    y=[results[c]["n_anomalies"] for c in contamination_levels],
    labels={"x": "Contamination", "y": "Anomalies Detected"},
    title="Anomaly Count by Contamination Level",
)
fig.show()
