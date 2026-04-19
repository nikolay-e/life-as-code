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
# # Exploratory Data Analysis
# Load latest snapshot, inspect all tables, summary statistics, distributions.

# %%
from src.loader import available_tables, db, load, manifest

tables = available_tables()
meta = manifest()
print(f"Snapshot: {meta.get('exported_at', 'unknown')}")
print(f"Status: {meta.get('status', 'unknown')}")
print(f"Tables: {len(tables)}")
print()

# %% [markdown]
# ## Table Overview

# %%
for t in tables:
    df = load(t)
    print(f"--- {t}: {df.shape[0]:,} rows × {df.shape[1]} cols ---")

# %% [markdown]
# ## Data Coverage Timeline

# %%
import polars as pl
import plotly.express as px

coverage = []
for t in tables:
    if t.startswith("_prod_"):
        continue
    df = load(t)
    date_cols = [c for c in df.columns if "date" in c.lower()]
    if not date_cols:
        continue
    date_col = "date" if "date" in date_cols else date_cols[0]
    non_null = df.filter(pl.col(date_col).is_not_null())
    if non_null.height == 0:
        continue
    coverage.append(
        {
            "table": t,
            "min": str(non_null[date_col].min()),
            "max": str(non_null[date_col].max()),
            "rows": non_null.height,
        }
    )

coverage_df = pl.DataFrame(coverage).sort("min")
print(coverage_df)

# %% [markdown]
# ## Key Metric Distributions

# %%
sleep = load("sleep")
if sleep.height > 0:
    fig = px.histogram(
        sleep.to_pandas(),
        x="total_sleep_minutes",
        nbins=40,
        title="Sleep Duration Distribution (minutes)",
    )
    fig.show()

# %%
hrv = load("hrv")
if hrv.height > 0:
    fig = px.histogram(
        hrv.to_pandas(), x="hrv_avg", nbins=40, title="HRV Distribution (ms)"
    )
    fig.show()

# %%
hr = load("heart_rate")
if hr.height > 0:
    fig = px.histogram(
        hr.to_pandas(), x="resting_hr", nbins=40, title="Resting Heart Rate Distribution"
    )
    fig.show()

# %%
weight = load("weight")
if weight.height > 0:
    fig = px.line(
        weight.sort("date").to_pandas(), x="date", y="weight_kg", title="Weight Over Time"
    )
    fig.show()

# %% [markdown]
# ## Missing Data Analysis

# %%
for t in ["sleep", "hrv", "heart_rate", "stress", "steps", "energy", "weight"]:
    df = load(t)
    if df.height == 0:
        print(f"{t}: empty")
        continue
    null_pcts = {
        col: round(df[col].null_count() / df.height * 100, 1)
        for col in df.columns
        if df[col].null_count() > 0
    }
    if null_pcts:
        print(f"\n{t} — columns with nulls:")
        for col, pct in sorted(null_pcts.items(), key=lambda x: -x[1]):
            print(f"  {col}: {pct}%")

# %% [markdown]
# ## SQL Exploration with DuckDB

# %%
conn = db()
conn.sql(
    """
    SELECT
        s.date,
        s.total_sleep_minutes,
        h.hrv_avg,
        hr.resting_hr
    FROM sleep s
    LEFT JOIN hrv h USING (date, user_id)
    LEFT JOIN heart_rate hr USING (date, user_id)
    ORDER BY s.date DESC
    LIMIT 20
    """
).show()

# %%
