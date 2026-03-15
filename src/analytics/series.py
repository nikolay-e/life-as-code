from __future__ import annotations

from datetime import date

from .constants import METRIC_AGGREGATION
from .date_utils import (
    day_number,
    filter_by_window,
    filter_by_window_range,
    to_day_key,
)
from .types import DataPoint


def to_daily_series(data: list[DataPoint], method: str = "last") -> list[DataPoint]:
    sorted_data = sorted(
        [d for d in data if d.value is not None],
        key=lambda d: day_number(d.date),
    )

    day_map: dict[str, list[float]] = {}
    for d in sorted_data:
        dk = to_day_key(d.date)
        if d.value is not None:
            day_map.setdefault(dk, []).append(d.value)

    result: list[DataPoint] = []
    for date_key, values in day_map.items():
        if not values:
            continue
        if method == "mean":
            aggregated = sum(values) / len(values)
        elif method == "max":
            aggregated = max(values)
        elif method == "sum":
            aggregated = sum(values)
        else:
            aggregated = values[-1]
        result.append(DataPoint(date=date_key, value=aggregated))

    return sorted(result, key=lambda d: d.date)


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
