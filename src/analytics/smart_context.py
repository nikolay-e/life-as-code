from __future__ import annotations

from .types import HealthAnalysis


def _build_health_score_ctx(analysis: HealthAnalysis) -> dict:
    hs = analysis.health_score
    hs_ctx: dict = {
        "overall": hs.overall,
        "recovery_core": hs.recovery_core,
        "training_load": hs.training_load,
        "behavior_support": hs.behavior_support,
    }
    notable = [
        {
            "name": c.name,
            "z": c.goodness_z_score,
            "raw_z": c.raw_z_score,
            "confidence": c.confidence,
            "source": c.source,
        }
        for c in hs.contributors
        if c.goodness_z_score is not None
        and abs(c.goodness_z_score) >= 0.5
        and c.gate_factor >= 0.1
    ]
    if notable:
        hs_ctx["notable_contributors"] = notable
    gated = [
        {"name": c.name, "reason": c.gate_reason}
        for c in hs.contributors
        if c.gate_factor < 0.1 and c.gate_reason
    ]
    if gated:
        hs_ctx["gated"] = gated
    if hs.data_confidence is not None:
        hs_ctx["data_confidence"] = round(hs.data_confidence, 2)
    return hs_ctx


def _add_clinical_signals(ctx: dict, analysis: HealthAnalysis) -> None:
    ca = analysis.clinical_alerts
    if ca.any_alert:
        ctx["clinical_alerts"] = ca.model_dump(exclude_none=True)
    if analysis.overreaching.risk_level in ("high", "critical"):
        ctx["overreaching"] = analysis.overreaching.model_dump(exclude_none=True)
    if analysis.illness_risk.risk_level in ("moderate", "high"):
        ctx["illness_risk"] = analysis.illness_risk.model_dump(exclude_none=True)
    if analysis.decorrelation.is_decorrelated:
        ctx["decorrelation"] = analysis.decorrelation.model_dump(exclude_none=True)


def _add_significant_correlations(ctx: dict, analysis: HealthAnalysis) -> None:
    corr = analysis.correlations
    sig_corrs = {}
    if corr.hrv_rhr_p_value is not None and corr.hrv_rhr_p_value < 0.05:
        sig_corrs["hrv_rhr"] = corr.hrv_rhr_correlation
    if corr.sleep_hrv_p_value is not None and corr.sleep_hrv_p_value < 0.05:
        sig_corrs["sleep_hrv_lag"] = corr.sleep_hrv_lag_correlation
    if corr.strain_recovery_p_value is not None and corr.strain_recovery_p_value < 0.05:
        sig_corrs["strain_recovery"] = corr.strain_recovery_correlation
    if sig_corrs:
        ctx["significant_correlations"] = sig_corrs


def _add_anomalies_ctx(ctx: dict, analysis: HealthAnalysis, max_anomalies: int) -> None:
    anomalies = analysis.anomalies
    if anomalies.anomaly_count <= 0:
        return
    anomaly_ctx = {
        "count": anomalies.anomaly_count,
        "has_recent": anomalies.has_recent_anomaly,
        "items": [
            a.model_dump(exclude_none=True) for a in anomalies.anomalies[:max_anomalies]
        ],
    }
    if anomalies.most_severe:
        anomaly_ctx["most_severe"] = anomalies.most_severe.model_dump(exclude_none=True)
    ctx["anomalies"] = anomaly_ctx


def _add_day_over_day_ctx(ctx: dict, analysis: HealthAnalysis) -> None:
    dod = analysis.day_over_day
    notable_dod = {}
    for field_name in ["hrv", "rhr", "sleep", "recovery", "steps", "weight", "strain"]:
        delta_obj = getattr(dod, field_name)
        if delta_obj.delta_percent is not None and abs(delta_obj.delta_percent) >= 10:
            notable_dod[field_name] = {
                "latest": delta_obj.latest,
                "previous": delta_obj.previous,
                "delta_pct": round(delta_obj.delta_percent, 1),
                "gap_days": delta_obj.gap_days,
            }
    if notable_dod:
        ctx["day_over_day"] = notable_dod


def _add_ml_insights_ctx(
    ctx: dict, analysis: HealthAnalysis, max_anomalies: int
) -> None:
    ml = analysis.ml_insights
    if not ml:
        return
    ml_ctx = {}
    if ml.has_active_forecasts:
        ml_ctx["forecasts"] = [f.model_dump(exclude_none=True) for f in ml.forecasts]
    if ml.has_recent_ml_anomalies:
        ml_ctx["ml_anomalies"] = [
            a.model_dump(exclude_none=True) for a in ml.ml_anomalies[:max_anomalies]
        ]
    if ml_ctx:
        ctx["ml_insights"] = ml_ctx


def build_smart_context(analysis: HealthAnalysis, max_anomalies: int = 3) -> dict:
    ctx: dict = {}

    ctx["health_score"] = _build_health_score_ctx(analysis)

    _add_if_notable_recovery(ctx, analysis)
    _add_if_notable_sleep(ctx, analysis)
    _add_if_notable_activity(ctx, analysis)
    _add_if_notable_weight(ctx, analysis)
    _add_if_notable_calories(ctx, analysis)
    _add_if_notable_energy_balance(ctx, analysis)

    _add_clinical_signals(ctx, analysis)
    _add_significant_correlations(ctx, analysis)

    vel = analysis.velocity
    active_vel = {
        k: v for k, v in vel.interpretation.items() if v is not None and v != "stable"
    }
    if active_vel:
        ctx["velocity_trends"] = active_vel

    rc = analysis.recovery_capacity
    if rc.avg_recovery_days is not None:
        ctx["recovery_capacity"] = rc.model_dump(exclude_none=True)

    _add_anomalies_ctx(ctx, analysis, max_anomalies)
    _add_day_over_day_ctx(ctx, analysis)

    if analysis.recent_days:
        ctx["recent_days"] = [
            d.model_dump(exclude_none=True) for d in analysis.recent_days
        ]

    _add_ml_insights_ctx(ctx, analysis, max_anomalies)

    ctx["day_completeness"] = analysis.day_completeness

    if analysis.data_source_summary:
        ctx["data_source_summary"] = [
            s.model_dump(exclude_none=True) for s in analysis.data_source_summary
        ]

    return ctx


def _add_if_notable_recovery(ctx: dict, analysis: HealthAnalysis) -> None:
    rm = analysis.recovery_metrics
    if (
        (rm.hrv_rhr_imbalance is not None and abs(rm.hrv_rhr_imbalance) > 0.5)
        or (rm.stress_trend is not None and abs(rm.stress_trend) > 0.3)
        or (rm.recovery_cv is not None and rm.recovery_cv > 0.3)
    ):
        ctx["recovery_metrics"] = rm.model_dump(exclude_none=True)


def _add_if_notable_sleep(ctx: dict, analysis: HealthAnalysis) -> None:
    sm = analysis.sleep_metrics
    if (
        abs(sm.sleep_debt_short) > 30
        or sm.sleep_cv > 0.2
        or sm.sleep_surplus_short > 60
    ):
        ctx["sleep_metrics"] = sm.model_dump(exclude_none=True)


def _add_if_notable_activity(ctx: dict, analysis: HealthAnalysis) -> None:
    am = analysis.activity_metrics
    if (am.acwr is not None and (am.acwr < 0.8 or am.acwr > 1.3)) or (
        am.steps_change is not None and abs(am.steps_change) > 20
    ):
        ctx["activity_metrics"] = am.model_dump(exclude_none=True)


def _add_if_notable_weight(ctx: dict, analysis: HealthAnalysis) -> None:
    wm = analysis.weight_metrics
    if (
        wm.period_change is not None and abs(wm.period_change) > 0.5
    ) or wm.volatility_short > 0.5:
        ctx["weight_metrics"] = wm.model_dump(exclude_none=True)


def _add_if_notable_calories(ctx: dict, analysis: HealthAnalysis) -> None:
    cm = analysis.calories_metrics
    if (cm.z_score is not None and abs(cm.z_score) > 1.0) or cm.trend in (
        "increasing",
        "decreasing",
    ):
        ctx["calories_metrics"] = cm.model_dump(exclude_none=True)


def _add_if_notable_energy_balance(ctx: dict, analysis: HealthAnalysis) -> None:
    eb = analysis.energy_balance
    if eb.balance_signal in ("surplus_confirmed", "deficit_confirmed"):
        ctx["energy_balance"] = eb.model_dump(exclude_none=True)
