import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from analytics.constants import WHOOP_MAX_STRAIN
from analytics.fusion import (
    blended_merge,
    normalize_garmin_strain_to_whoop_scale,
)
from analytics.longevity import (
    _score_sleep,
    calculate_biological_age,
    calculate_longevity_score,
)
from analytics.metrics import (
    calculate_baseline_metrics,
    should_use_today_metric,
)
from analytics.types import DataPoint


def _make_points(days=30, base=50.0, noise=0.0, ref_date=None):
    end = ref_date or date.today()
    return [
        DataPoint(
            date=(end - timedelta(days=days - 1 - i)).isoformat(),
            value=base + (noise * (i % 3 - 1)),
        )
        for i in range(days)
    ]


class TestSleepScoringUCurve:
    def test_optimal_sleep_7_5h(self):
        data = _make_points(30, base=450.0)
        score = _score_sleep(data, 30)
        assert score is not None
        assert score > 90

    def test_short_sleep_6h(self):
        data = _make_points(30, base=360.0)
        score = _score_sleep(data, 30)
        assert score is not None
        assert score < 90

    def test_mild_oversleep_8_5h(self):
        data = _make_points(30, base=510.0)
        score = _score_sleep(data, 30)
        assert score is not None
        assert score > 85

    def test_moderate_oversleep_9h(self):
        data = _make_points(30, base=540.0)
        score = _score_sleep(data, 30)
        assert score is not None
        assert score > 80

    def test_excessive_oversleep_10h(self):
        data = _make_points(30, base=600.0)
        score = _score_sleep(data, 30)
        assert score is not None
        assert score < 85


class TestStrainNormalization:
    def test_clamped_to_whoop_range(self):
        garmin = _make_points(20, base=300.0, noise=50.0)
        whoop = _make_points(20, base=10.0, noise=3.0)
        normalized, success = normalize_garmin_strain_to_whoop_scale(garmin, whoop)
        assert success
        for p in normalized:
            if p.value is not None:
                assert 0.0 <= p.value <= WHOOP_MAX_STRAIN

    def test_insufficient_overlap_returns_original(self):
        garmin = _make_points(5, base=300.0)
        whoop = _make_points(5, base=10.0)
        normalized, success = normalize_garmin_strain_to_whoop_scale(garmin, whoop)
        assert not success
        assert len(normalized) == len(garmin)

    def test_blended_merge_strain_clamped(self):
        garmin = _make_points(20, base=400.0, noise=50.0)
        whoop = _make_points(20, base=15.0, noise=3.0)
        result = blended_merge(garmin, whoop, "strain")
        for p in result:
            if p.value is not None:
                assert 0.0 <= p.value <= WHOOP_MAX_STRAIN


class TestZScoreGate:
    def test_insufficient_data_no_zscore(self):
        data = _make_points(10, base=50.0)
        baseline = calculate_baseline_metrics(
            data,
            baseline_window=42,
            short_term_window=7,
            metric_name="hrv",
            trend_window=7,
        )
        assert baseline.z_score is None

    def test_sufficient_data_has_zscore(self):
        data = _make_points(30, base=50.0, noise=5.0)
        baseline = calculate_baseline_metrics(
            data,
            baseline_window=42,
            short_term_window=7,
            metric_name="hrv",
            trend_window=7,
        )
        assert baseline.z_score is not None


class TestTodayDataHandling:
    def test_instantaneous_metric_always_included(self):
        today = date.today().isoformat()
        data = [DataPoint(date=today, value=65.0)]
        use, _, msg = should_use_today_metric(data, "hrv")
        assert use is True
        assert "instantaneous" in msg

    def test_accumulating_metric_respects_threshold(self):
        today = date.today().isoformat()
        data = [DataPoint(date=today, value=5000.0)]
        use, _, _ = should_use_today_metric(data, "steps")
        assert isinstance(use, bool)

    def test_no_data_returns_false(self):
        data = []
        use, _, _ = should_use_today_metric(data, "hrv")
        assert use is False


class TestBiologicalAge:
    def test_low_rhr_younger(self):
        rhr_data = _make_points(30, base=50.0)
        result = calculate_biological_age(
            hrv_data=[],
            vo2_max_data=[],
            rhr_data=rhr_data,
            fitness_age_data=[],
            recovery_data=[],
            chronological_age=35.0,
        )
        rhr_comp = next((c for c in result.components if c.name == "rhr_age"), None)
        assert rhr_comp is not None
        assert rhr_comp.delta < 0

    def test_high_rhr_older(self):
        rhr_data = _make_points(30, base=80.0)
        result = calculate_biological_age(
            hrv_data=[],
            vo2_max_data=[],
            rhr_data=rhr_data,
            fitness_age_data=[],
            recovery_data=[],
            chronological_age=35.0,
        )
        rhr_comp = next((c for c in result.components if c.name == "rhr_age"), None)
        assert rhr_comp is not None
        assert rhr_comp.delta > 0


class TestLongevityScore:
    def test_all_scores_in_range(self):
        data = _make_points(90, base=50.0, noise=5.0)
        sleep_data = _make_points(90, base=450.0, noise=10.0)
        steps_data = _make_points(90, base=10000.0, noise=1000.0)
        weight_data = _make_points(90, base=80.0, noise=0.5)
        result = calculate_longevity_score(
            vo2_max_data=data,
            hrv_data=data,
            recovery_data=data,
            sleep_data=sleep_data,
            weight_data=weight_data,
            body_fat_data=[],
            steps_data=steps_data,
            workout_dates=data,
            chronological_age=35.0,
        )
        if result.overall is not None:
            assert 0 <= result.overall <= 100
        for field in [
            "cardiorespiratory",
            "recovery_resilience",
            "sleep_optimization",
            "body_composition",
            "activity_consistency",
        ]:
            val = getattr(result, field)
            if val is not None:
                assert 0 <= val <= 100


class TestDataFusionBlending:
    def test_overlapping_sources_blended(self):
        garmin = _make_points(20, base=60.0, noise=5.0)
        whoop = _make_points(20, base=58.0, noise=5.0)
        result = blended_merge(garmin, whoop, "hrv")
        blended_points = [p for p in result if p.provider == "blended"]
        assert len(blended_points) > 0

    def test_single_source_not_blended(self):
        garmin = _make_points(20, base=60.0)
        whoop = []
        result = blended_merge(garmin, whoop, "hrv")
        for p in result:
            assert p.provider == "garmin"
