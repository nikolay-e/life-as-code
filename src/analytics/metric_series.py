from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from .constants import METRIC_AGGREGATION
from .date_utils import filter_by_window, filter_by_window_range, to_day_key
from .types import BaselineMetrics, BaselineOptions, DataPoint, UnifiedMetricPoint


@dataclass
class MetricSeries:
    metric: str
    source: str
    points: list[DataPoint]
    unit: str = ""
    _daily_cache: dict[str, MetricSeries] = field(
        default_factory=dict, repr=False, compare=False
    )
    _window_cache: dict[tuple, MetricSeries] = field(
        default_factory=dict, repr=False, compare=False
    )
    _baseline_cache: dict[tuple, BaselineMetrics] = field(
        default_factory=dict, repr=False, compare=False
    )

    def __post_init__(self):
        self.points = sorted(
            [p for p in self.points if p.value is not None],
            key=lambda p: p.date,
        )

    def daily(self, method: str | None = None) -> MetricSeries:
        m = method or METRIC_AGGREGATION.get(self.metric, "last")
        cached = self._daily_cache.get(m)
        if cached is not None:
            return cached
        from .series import to_daily_series

        daily_points = to_daily_series(self.points, m)
        result = MetricSeries(
            metric=self.metric, source=self.source, points=daily_points, unit=self.unit
        )
        self._daily_cache[m] = result
        return result

    def window(self, days: int, ref_date: date | None = None) -> MetricSeries:
        key = (days, ref_date)
        cached = self._window_cache.get(key)
        if cached is not None:
            return cached
        filtered = filter_by_window(self.points, days, ref_date=ref_date)
        result = MetricSeries(
            metric=self.metric, source=self.source, points=filtered, unit=self.unit
        )
        self._window_cache[key] = result
        return result

    def window_range(
        self, days_back: int, days_back_end: int, ref_date: date | None = None
    ) -> MetricSeries:
        filtered = filter_by_window_range(
            self.points, days_back, days_back_end, ref_date=ref_date
        )
        return MetricSeries(
            metric=self.metric, source=self.source, points=filtered, unit=self.unit
        )

    def values(self) -> list[float]:
        return [p.value for p in self.points if p.value is not None]

    def mean(self) -> float | None:
        vals = self.values()
        return sum(vals) / len(vals) if vals else None

    def latest(self, ref_date: date | None = None) -> DataPoint | None:
        if not self.points:
            return None
        if ref_date:
            ref_str = ref_date.isoformat()
            candidates = [
                p for p in self.points if p.date <= ref_str and p.value is not None
            ]
            return candidates[-1] if candidates else None
        for p in reversed(self.points):
            if p.value is not None:
                return p
        return None

    def by_day_map(self) -> dict[str, float]:
        result: dict[str, float] = {}
        for p in self.points:
            if p.value is not None:
                result[to_day_key(p.date)] = p.value
        return result

    def baseline(
        self,
        baseline_window: int,
        short_term_window: int,
        trend_window: int = 7,
        options: BaselineOptions | None = None,
        ref_date: date | None = None,
    ) -> BaselineMetrics:
        from .metrics import _calculate_baseline_metrics_impl

        opts_key = (
            (
                options.exclude_recent_days_from_baseline,
                options.regression_uses_real_days,
                options.winsorize_trend,
            )
            if options
            else None
        )
        cache_key = (
            baseline_window,
            short_term_window,
            trend_window,
            opts_key,
            ref_date,
        )
        cached = self._baseline_cache.get(cache_key)
        if cached is not None:
            return cached
        result = _calculate_baseline_metrics_impl(
            self.points,
            baseline_window,
            short_term_window,
            self.metric,
            trend_window,
            options,
            ref_date,
        )
        self._baseline_cache[cache_key] = result
        return result

    def __len__(self) -> int:
        return len(self.points)

    def __bool__(self) -> bool:
        return len(self.points) > 0


@dataclass
class FusedMetric:
    unified: list[UnifiedMetricPoint]
    blended: MetricSeries
    garmin: MetricSeries | None = None
    whoop: MetricSeries | None = None

    def best_source(self) -> MetricSeries:
        if self.garmin and self.whoop:
            if len(self.garmin) > len(self.whoop):
                return self.garmin
            if len(self.whoop) > len(self.garmin):
                return self.whoop
            g = self.garmin.latest()
            w = self.whoop.latest()
            if g and w:
                return self.garmin if g.date >= w.date else self.whoop
            return self.garmin if g else self.whoop
        return self.garmin or self.whoop or self.blended


@dataclass
class FusedHealthData:
    hrv: FusedMetric
    sleep: FusedMetric
    resting_hr: FusedMetric
    strain: FusedMetric
    calories: FusedMetric
