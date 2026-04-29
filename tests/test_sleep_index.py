"""Integration tests for the local Sleep Index formula."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from analytics.sleep_index import SleepIndexInputs, compute_sleep_index


def _good_night() -> SleepIndexInputs:
    """A textbook excellent night: 8h total, 18% deep, 22% REM, 10min latency,
    HRV right at baseline. Eight Sleep also said the night was 90/95."""
    return SleepIndexInputs(
        routine_score=95,
        quality_score=90,
        total_sleep_minutes=480,  # 8h
        time_in_bed_minutes=505,  # eff ~95%
        deep_minutes=86.4,  # 18% of 480
        rem_minutes=105.6,  # 22% of 480
        latency_asleep_minutes=10,
        hrv_overnight_ms=55,
        hrv_baseline_mean_ms=55,
        hrv_baseline_std_ms=8,
    )


class TestSleepIndex:
    def test_excellent_night_scores_high(self):
        score = compute_sleep_index(_good_night())
        assert score is not None
        assert score >= 90

    def test_short_sleep_drags_down(self):
        bad = SleepIndexInputs(
            **{**_good_night().__dict__, "total_sleep_minutes": 240},
        )
        bad = SleepIndexInputs(
            routine_score=95,
            quality_score=90,
            total_sleep_minutes=240,  # 4h
            time_in_bed_minutes=270,
            deep_minutes=43,
            rem_minutes=53,
            latency_asleep_minutes=10,
            hrv_overnight_ms=55,
            hrv_baseline_mean_ms=55,
            hrv_baseline_std_ms=8,
        )
        score = compute_sleep_index(bad)
        good_score = compute_sleep_index(_good_night())
        assert score is not None
        assert good_score is not None
        assert score < good_score
        assert score < 80

    def test_latency_penalty(self):
        long_latency = SleepIndexInputs(
            routine_score=95,
            quality_score=90,
            total_sleep_minutes=480,
            time_in_bed_minutes=600,  # +60min lying awake = lower efficiency
            deep_minutes=86,
            rem_minutes=106,
            latency_asleep_minutes=60,
            hrv_overnight_ms=55,
            hrv_baseline_mean_ms=55,
            hrv_baseline_std_ms=8,
        )
        score = compute_sleep_index(long_latency)
        good_score = compute_sleep_index(_good_night())
        assert score is not None and good_score is not None
        assert score < good_score

    def test_hrv_above_baseline_helps(self):
        high_hrv = SleepIndexInputs(
            **{**_good_night().__dict__, "hrv_overnight_ms": 75},  # +2.5σ
        )
        score = compute_sleep_index(high_hrv)
        baseline = compute_sleep_index(_good_night())
        assert score is not None and baseline is not None
        assert score >= baseline

    def test_garmin_only_night_no_routine_no_quality(self):
        """When Eight Sleep is offline (no routine/quality), formula still produces
        a sensible score from duration + efficiency + architecture + latency + hrv."""
        garmin_only = SleepIndexInputs(
            routine_score=None,
            quality_score=None,
            total_sleep_minutes=470,
            time_in_bed_minutes=500,
            deep_minutes=82,
            rem_minutes=104,
            latency_asleep_minutes=12,
            hrv_overnight_ms=55,
            hrv_baseline_mean_ms=55,
            hrv_baseline_std_ms=8,
        )
        score = compute_sleep_index(garmin_only)
        assert score is not None
        assert 70 <= score <= 100

    def test_zero_data_returns_none(self):
        empty = SleepIndexInputs(
            routine_score=None,
            quality_score=None,
            total_sleep_minutes=None,
            time_in_bed_minutes=None,
            deep_minutes=None,
            rem_minutes=None,
            latency_asleep_minutes=None,
            hrv_overnight_ms=None,
            hrv_baseline_mean_ms=None,
            hrv_baseline_std_ms=None,
        )
        assert compute_sleep_index(empty) is None

    def test_score_is_clamped_to_0_100(self):
        score = compute_sleep_index(_good_night())
        assert score is not None
        assert 0.0 <= score <= 100.0

    def test_partial_data_redistributes_weights(self):
        """Routine null but quality+duration+architecture present → still ~0-100."""
        no_routine = SleepIndexInputs(
            routine_score=None,
            quality_score=85,
            total_sleep_minutes=460,
            time_in_bed_minutes=490,
            deep_minutes=82,
            rem_minutes=100,
            latency_asleep_minutes=15,
            hrv_overnight_ms=52,
            hrv_baseline_mean_ms=55,
            hrv_baseline_std_ms=8,
        )
        score = compute_sleep_index(no_routine)
        assert score is not None
        assert 0.0 <= score <= 100.0

    @pytest.mark.parametrize(
        "minutes, expected_min, expected_max",
        [
            (480, 95, 100),  # 8h plateau
            (430, 95, 100),  # 7h12 plateau (in [420, 540])
            (300, 0, 50),  # 5h significantly short
            (200, 0, 0),  # under floor
            (700, 0, 0),  # way over ceiling
        ],
    )
    def test_duration_bands(self, minutes, expected_min, expected_max):
        from analytics.sleep_index import _duration_score

        score = _duration_score(minutes)
        assert score is not None
        assert expected_min <= score <= expected_max
