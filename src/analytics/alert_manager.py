from __future__ import annotations

import logging
from collections.abc import Callable

from sqlalchemy.orm import Session

from .date_utils import utcnow
from .types import HealthAnalysis

logger = logging.getLogger(__name__)

ALERT_EXTRACTORS: list[tuple[str, str, Callable[[HealthAnalysis], dict | None]]] = []


def _register(alert_type: str, severity: str):
    def decorator(fn):
        ALERT_EXTRACTORS.append((alert_type, severity, fn))
        return fn

    return decorator


@_register("persistent_tachycardia", "alert")
def _check_tachycardia(analysis: HealthAnalysis) -> dict | None:
    ca = analysis.clinical_alerts
    if ca.persistent_tachycardia:
        return {"tachycardia_days": ca.tachycardia_days}
    return None


@_register("acute_hrv_drop", "critical")
def _check_hrv_drop(analysis: HealthAnalysis) -> dict | None:
    ca = analysis.clinical_alerts
    if ca.acute_hrv_drop:
        return {"hrv_drop_percent": ca.hrv_drop_percent}
    return None


@_register("progressive_weight_loss", "alert")
def _check_weight_loss(analysis: HealthAnalysis) -> dict | None:
    ca = analysis.clinical_alerts
    if ca.progressive_weight_loss:
        return {"weight_loss_percent": ca.weight_loss_percent}
    return None


@_register("severe_overtraining", "critical")
def _check_overtraining(analysis: HealthAnalysis) -> dict | None:
    ca = analysis.clinical_alerts
    if ca.severe_overtraining:
        return {"overtraining_score": ca.overtraining_score}
    return None


@_register("overreaching_high", "alert")
def _check_overreaching(analysis: HealthAnalysis) -> dict | None:
    o = analysis.overreaching
    if o.risk_level in ("high", "critical"):
        return {"score": o.score, "risk_level": o.risk_level}
    return None


@_register("illness_risk", "warning")
def _check_illness_risk(analysis: HealthAnalysis) -> dict | None:
    ir = analysis.illness_risk
    if ir.risk_level in ("moderate", "high"):
        return {
            "risk_level": ir.risk_level,
            "combined_deviation": ir.combined_deviation,
            "consecutive_days": ir.consecutive_days_elevated,
        }
    return None


def process_alerts(db: Session, user_id: int, analysis: HealthAnalysis) -> list[dict]:
    from models import ClinicalAlertEvent

    now = utcnow()
    fired_types: set[str] = set()
    new_alerts: list[dict] = []

    for alert_type, severity, extractor in ALERT_EXTRACTORS:
        details = extractor(analysis)
        if details is None:
            continue

        fired_types.add(alert_type)

        existing = (
            db.query(ClinicalAlertEvent)
            .filter_by(user_id=user_id, alert_type=alert_type)
            .filter(ClinicalAlertEvent.status.in_(["open", "acknowledged"]))
            .first()
        )

        if existing:
            existing.last_detected_at = now
            existing.details_json = details
            if severity_rank(severity) > severity_rank(existing.severity):
                existing.severity = severity
        else:
            event = ClinicalAlertEvent(
                user_id=user_id,
                alert_type=alert_type,
                severity=severity,
                status="open",
                details_json=details,
                first_detected_at=now,
                last_detected_at=now,
            )
            db.add(event)
            new_alerts.append(
                {"type": alert_type, "severity": severity, "details": details}
            )

    open_alerts = (
        db.query(ClinicalAlertEvent)
        .filter_by(user_id=user_id)
        .filter(ClinicalAlertEvent.status.in_(["open", "acknowledged"]))
        .all()
    )
    for alert in open_alerts:
        if alert.alert_type not in fired_types:
            alert.status = "resolved"
            alert.resolved_at = now

    db.flush()
    return new_alerts


def get_active_alerts(db: Session, user_id: int) -> list[dict]:
    from models import ClinicalAlertEvent

    alerts = (
        db.query(ClinicalAlertEvent)
        .filter_by(user_id=user_id)
        .filter(ClinicalAlertEvent.status.in_(["open", "acknowledged"]))
        .order_by(ClinicalAlertEvent.last_detected_at.desc())
        .all()
    )
    return [
        {
            "id": a.id,
            "type": a.alert_type,
            "severity": a.severity,
            "status": a.status,
            "first_detected": (
                a.first_detected_at.isoformat() if a.first_detected_at else None
            ),
            "last_detected": (
                a.last_detected_at.isoformat() if a.last_detected_at else None
            ),
            "details": a.details_json,
        }
        for a in alerts
    ]


def acknowledge_alert(db: Session, alert_id: int) -> bool:
    from models import ClinicalAlertEvent

    alert = db.query(ClinicalAlertEvent).get(alert_id)
    if not alert or alert.status != "open":
        return False
    alert.status = "acknowledged"
    alert.acknowledged_at = utcnow()
    db.flush()
    return True


def severity_rank(severity: str) -> int:
    return {"info": 0, "warning": 1, "alert": 2, "critical": 3}.get(severity, 0)
