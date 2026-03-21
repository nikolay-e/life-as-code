from __future__ import annotations

from datetime import date

import pandas as pd

from .constants import METRIC_AGGREGATION
from .date_utils import (
    filter_by_window,
    filter_by_window_range,
    to_day_key,
)
from .types import DataPoint


def to_daily_series(data: list[DataPoint], method: str = "last") -> list[DataPoint]:
    rows = [
        {"date": to_day_key(d.date), "value": d.value}
        for d in data
        if d.value is not None
    ]
    if not rows:
        return []

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")

    agg_map = {"mean": "mean", "max": "max", "sum": "sum", "last": "last"}
    agg_fn = agg_map.get(method, "last")
    daily = df.groupby("date")["value"].agg(agg_fn).reset_index()

    return [
        DataPoint(date=row["date"].strftime("%Y-%m-%d"), value=float(row["value"]))
        for row in daily.to_dict("records")
    ]


def to_daily_series_for_metric(data: list[DataPoint], metric: str) -> list[DataPoint]:
    method = METRIC_AGGREGATION.get(metric, "last")
    return to_daily_series(data, method)


def get_window_values(
    data: list[DataPoint], window_days: int, ref_date: date | None = None
) -> list[float]:
    return [
        d.value
        for d in filter_by_window(data, window_days, ref_date=ref_date)
        if d.value is not None
    ]


def get_window_range_values(
    data: list[DataPoint],
    days_back: int,
    days_back_end: int,
    ref_date: date | None = None,
) -> list[float]:
    return [
        d.value
        for d in filter_by_window_range(
            data, days_back, days_back_end, ref_date=ref_date
        )
        if d.value is not None
    ]
