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
# # Time Series Forecasting with Chronos
# Local forecasting experiments. Requires: `uv sync --extra forecasting`

# %%
import polars as pl
import plotly.graph_objects as go

from src.config import detect_device
from src.loader import load

device = detect_device()
print(f"Device: {device}")

# %% [markdown]
# ## Load and Prepare Data

# %%
METRIC = "hrv_avg"
TABLE = "hrv"

raw = load(TABLE).sort("date")
series = raw.filter(
    pl.col(METRIC).is_not_null()
).select(["date", METRIC])
print(f"Series length: {series.height} days")
series.tail(10)

# %% [markdown]
# ## Train/Test Split

# %%
FORECAST_HORIZON = 14
train = series.head(series.height - FORECAST_HORIZON)
test = series.tail(FORECAST_HORIZON)
print(f"Train: {train.height} days, Test: {test.height} days")

# %% [markdown]
# ## Load Chronos Pipeline

# %%
import torch
from chronos import BaseChronosPipeline

pipeline = BaseChronosPipeline.from_pretrained(
    "amazon/chronos-bolt-base",
    device_map=device,
    dtype=torch.float32,
)

# %% [markdown]
# ## Generate Forecast

# %%
context = torch.tensor(
    train[METRIC].to_list(), dtype=torch.float32
).unsqueeze(0)
quantiles, mean = pipeline.predict_quantiles(
    context,
    prediction_length=FORECAST_HORIZON,
    quantile_levels=[0.1, 0.5, 0.9],
)

p10 = quantiles[0, :, 0].tolist()
p50 = quantiles[0, :, 1].tolist()
p90 = quantiles[0, :, 2].tolist()

# %% [markdown]
# ## Plot Forecast vs Actuals

# %%
train_dates = train["date"].to_list()
test_dates = test["date"].to_list()
actual_vals = test[METRIC].to_list()

fig = go.Figure()
fig.add_trace(go.Scatter(
    x=train_dates[-60:],
    y=train[METRIC].to_list()[-60:],
    mode="lines",
    name="Historical",
    line=dict(color="gray"),
))
fig.add_trace(go.Scatter(
    x=test_dates,
    y=actual_vals,
    mode="lines+markers",
    name="Actual",
    line=dict(color="blue"),
))
fig.add_trace(go.Scatter(
    x=test_dates,
    y=p50,
    mode="lines",
    name="Forecast (p50)",
    line=dict(color="red"),
))
fig.add_trace(go.Scatter(
    x=test_dates + test_dates[::-1],
    y=p90 + p10[::-1],
    fill="toself",
    fillcolor="rgba(255,0,0,0.1)",
    line=dict(color="rgba(255,0,0,0)"),
    name="p10-p90 range",
))
fig.update_layout(
    title=f"Chronos Forecast: {METRIC} ({FORECAST_HORIZON}-day)",
    xaxis_title="Date",
    yaxis_title=METRIC,
)
fig.show()

# %% [markdown]
# ## Forecast Accuracy

# %%
import numpy as np

actual = np.array(actual_vals)
predicted = np.array(p50)

mae = np.mean(np.abs(actual - predicted))
rmse = np.sqrt(np.mean((actual - predicted) ** 2))
nonzero = actual != 0
map = np.mean(np.abs((actual[nonzero] - predicted[nonzero]) / actual[nonzero])) * 100

print(f"MAE:  {mae:.2f}")
print(f"RMSE: {rmse:.2f}")
print(f"MAP: {map:.1f}%")

# %% [markdown]
# ## Compare with Production Forecasts

# %%
try:
    prod_preds = load("_prod_predictions")
    prod_metric = prod_preds.filter(
        pl.col("metric") == METRIC.replace("_avg", "")
    )
    if prod_metric.height > 0:
        print(
            f"Production forecasts for {METRIC}: "
            f"{prod_metric.height} rows"
        )
        print(prod_metric.sort("target_date").tail(10))
    else:
        print(f"No production forecasts found for {METRIC}")
except FileNotFoundError:
    print(
        "No _prod_predictions snapshot "
        "- run export with default tables"
    )
