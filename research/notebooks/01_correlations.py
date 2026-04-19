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
# # Cross-Metric Correlations & Lag Analysis
# Explore relationships between health metrics.

# %%
import polars as pl
import plotly.express as px
from scipy import stats

from src.loader import db

conn = db()

# %% [markdown]
# ## Build Unified Daily Dataset

# %%
daily = conn.sql(
    """
    SELECT
        s.date,
        s.total_sleep_minutes,
        s.deep_minutes,
        s.rem_minutes,
        s.sleep_score,
        h.hrv_avg,
        hr.resting_hr,
        st.avg_stress,
        step.total_steps,
        e.active_energy,
        w.weight_kg
    FROM sleep s
    LEFT JOIN hrv h USING (date, user_id)
    LEFT JOIN heart_rate hr USING (date, user_id)
    LEFT JOIN stress st USING (date, user_id)
    LEFT JOIN steps step USING (date, user_id)
    LEFT JOIN energy e USING (date, user_id)
    LEFT JOIN weight w USING (date, user_id)
    ORDER BY s.date
    """
).pl()

print(f"Unified dataset: {daily.shape[0]} days × {daily.shape[1]} cols")
daily.head()

# %% [markdown]
# ## Correlation Matrix

# %%
numeric_cols = [
    c
    for c in daily.columns
    if c != "date"
    and daily[c].dtype in [pl.Float64, pl.Int64, pl.Float32, pl.Int32]
]
corr_df = daily.select(numeric_cols).to_pandas().corr()

fig = px.imshow(
    corr_df,
    text_auto=".2f",
    color_continuous_scale="RdBu_r",
    zmin=-1,
    zmax=1,
    title="Health Metrics Correlation Matrix",
)
fig.update_layout(width=800, height=700)
fig.show()

# %% [markdown]
# ## Lag Correlation: Sleep → Next-Day HRV

# %%
lag_df = daily.filter(
    pl.col("total_sleep_minutes").is_not_null()
    & pl.col("hrv_avg").is_not_null()
).sort("date")

if lag_df.height > 14:
    sleep_vals = lag_df["total_sleep_minutes"].to_list()[:-1]
    hrv_next = lag_df["hrv_avg"].to_list()[1:]

    r, p = stats.pearsonr(sleep_vals, hrv_next)
    print(f"Sleep → Next-day HRV: r={r:.3f}, p={p:.4f}")

    fig = px.scatter(
        x=sleep_vals,
        y=hrv_next,
        labels={"x": "Sleep (min)", "y": "Next-day HRV (ms)"},
        title=f"Sleep → Next-Day HRV (r={r:.3f}, p={p:.4f})",
        trendline="ols",
    )
    fig.show()

# %% [markdown]
# ## Multi-Lag Correlation Sweep

# %%
target_col = "hrv_avg"
feature_cols = [
    "total_sleep_minutes",
    "deep_minutes",
    "total_steps",
    "avg_stress",
    "active_energy",
]
max_lag = 7

lag_results = []

for feat in feature_cols:
    paired = daily.filter(
        pl.col(feat).is_not_null()
        & pl.col(target_col).is_not_null()
    ).sort("date")

    if paired.height < 14:
        continue

    feat_vals = paired[feat].to_list()
    target_vals = paired[target_col].to_list()

    for lag in range(max_lag + 1):
        n = len(feat_vals) - lag
        if n < 14:
            continue
        x = feat_vals[:n]
        y = target_vals[lag : lag + n]
        r, p = stats.pearsonr(x, y)
        lag_results.append({
            "feature": feat,
            "lag_days": lag,
            "r": round(r, 3),
            "p": round(p, 4),
        })

lag_corr = pl.DataFrame(lag_results)
print(lag_corr.sort(["feature", "lag_days"]))

# %% [markdown]
# ## Day-of-Week Patterns

# %%
daily_with_dow = daily.with_columns(
    pl.col("date").cast(pl.Date).dt.weekday().alias("weekday")
)

for metric in ["total_sleep_minutes", "hrv_avg", "total_steps"]:
    by_dow = (
        daily_with_dow.filter(pl.col(metric).is_not_null())
        .group_by("weekday")
        .agg(pl.col(metric).mean().alias("mean"))
        .sort("weekday")
    )
    if by_dow.height > 0:
        fig = px.bar(
            by_dow.to_pandas(),
            x="weekday",
            y="mean",
            title=f"{metric} by Day of Week (1=Mon, 7=Sun)",
        )
        fig.show()
