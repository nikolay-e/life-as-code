from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from analytics.date_utils import local_today
from database import get_db_session_context
from date_utils import parse_iso_date
from models import (
    HRV,
    Energy,
    GarminActivity,
    HealthEvent,
    HealthNote,
    HeartRate,
    Prediction,
    Protocol,
    Sleep,
    Steps,
    Weight,
    WorkoutSet,
)

HEALTH_EVENT_DOMAINS = [
    "substance",
    "therapy",
    "nutrition",
    "sleep",
    "stress",
    "environment",
    "symptom",
    "medication",
]
PROTOCOL_DOMAINS = [
    "supplement",
    "medication",
    "diet",
    "lifestyle",
    "training",
    "other",
]

TOOLS = [
    {
        "name": "query_health_data",
        "description": "Query the user's health database. Returns raw data for a specific metric and date range.",
        "input_schema": {
            "type": "object",
            "properties": {
                "metric": {
                    "type": "string",
                    "enum": [
                        "steps",
                        "sleep",
                        "heart_rate",
                        "hrv",
                        "weight",
                        "energy",
                        "workouts",
                        "strength",
                    ],
                },
                "start_date": {"type": "string", "description": "YYYY-MM-DD"},
                "end_date": {"type": "string", "description": "YYYY-MM-DD"},
                "aggregation": {
                    "type": "string",
                    "enum": ["daily", "weekly", "monthly"],
                },
            },
            "required": ["metric", "start_date", "end_date"],
        },
    },
    {
        "name": "get_predictions",
        "description": "Get ML forecasts for a health metric.",
        "input_schema": {
            "type": "object",
            "properties": {
                "metric": {
                    "type": "string",
                    "enum": ["weight", "hrv", "rhr", "sleep_total", "steps"],
                },
                "horizon_days": {"type": "integer", "enum": [1, 7, 14]},
            },
            "required": ["metric"],
        },
    },
    {
        "name": "compare_periods",
        "description": "Compare health metrics between two time periods.",
        "input_schema": {
            "type": "object",
            "properties": {
                "metric": {
                    "type": "string",
                    "enum": ["steps", "sleep", "heart_rate", "hrv", "weight"],
                },
                "period_a_start": {"type": "string"},
                "period_a_end": {"type": "string"},
                "period_b_start": {"type": "string"},
                "period_b_end": {"type": "string"},
            },
            "required": [
                "metric",
                "period_a_start",
                "period_a_end",
                "period_b_start",
                "period_b_end",
            ],
        },
    },
    {
        "name": "log_event",
        "description": (
            "Log a one-time or bounded health event — something that already happened. "
            "DISCRIMINATOR: past-simple verb ('took', 'had', 'drank', 'did') with no "
            "frequency word → use this tool (set end_ts=null for point event). "
            "Duration signal ('for 40 min', 'lasted 3 days', 'from X to Y') → set end_ts. "
            "DO NOT use for ongoing regimens — use log_protocol instead. "
            "When ambiguous, default to this tool and echo the classification in your reply "
            "so the user can correct it."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": (
                        "Short English canonical name. Examples: 'Alcohol', 'Sauna', "
                        "'Ibuprofen', 'Nausea', 'Fasting 16h', 'Cold Plunge'. "
                        "Use English even if user wrote in Russian."
                    ),
                },
                "domain": {
                    "type": "string",
                    "enum": HEALTH_EVENT_DOMAINS,
                    "description": (
                        "substance=alcohol/caffeine/recreational drugs; "
                        "therapy=sauna/cold plunge/massage/breathwork; "
                        "nutrition=meal/fast/diet episode; "
                        "sleep=nap/sleep restriction; "
                        "stress=acute stressor/meditation session; "
                        "environment=travel/altitude/heat; "
                        "symptom=pain/illness/fatigue; "
                        "medication=one-off dose"
                    ),
                },
                "start_ts": {
                    "type": "string",
                    "description": "ISO datetime or YYYY-MM-DD. Defaults to now if omitted.",
                },
                "end_ts": {
                    "type": "string",
                    "description": (
                        "ISO datetime or YYYY-MM-DD. Leave null for point events "
                        "(single occurrence with no meaningful duration). "
                        "Set for bounded durations: sauna sessions, illness episodes, fasting windows."
                    ),
                },
                "dosage": {
                    "type": "string",
                    "description": "e.g. '2 glasses', '400mg', '40 min'. Optional.",
                },
                "notes": {"type": "string", "description": "Brief context. Optional."},
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Free-form tags e.g. ['sleep', 'stress', 'alcohol']",
                },
            },
            "required": ["name", "domain"],
        },
    },
    {
        "name": "log_protocol",
        "description": (
            "Start an ongoing health regimen — something the user is doing regularly going forward. "
            "DISCRIMINATOR: ingressive verb ('started', 'began', 'now taking') OR "
            "explicit frequency ('daily', '3x/week', 'every morning') → use this tool. "
            "NOT for things that already happened — use log_event instead."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "e.g. 'Magnesium Glycinate', 'Carnivore Diet', 'Creatine', 'SSRIs'",
                },
                "domain": {
                    "type": "string",
                    "enum": PROTOCOL_DOMAINS,
                },
                "start_date": {
                    "type": "string",
                    "description": "YYYY-MM-DD. Defaults to today if omitted.",
                },
                "dosage": {"type": "string", "description": "e.g. '400mg', '5g daily'"},
                "frequency": {
                    "type": "string",
                    "description": "e.g. 'daily', 'twice daily', 'weekly'",
                },
                "notes": {"type": "string"},
                "tags": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["name", "domain"],
        },
    },
    {
        "name": "stop_protocol",
        "description": (
            "Stop an active protocol by setting its end_date. "
            "Use when user says they stopped, finished, or are no longer doing something. "
            "Call list_recent_logs first to get the protocol_id if unsure."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "protocol_id": {
                    "type": "integer",
                    "description": "ID from list_recent_logs. Preferred over name lookup.",
                },
                "name": {
                    "type": "string",
                    "description": "Fuzzy-match active protocol by name if id not known.",
                },
                "end_date": {
                    "type": "string",
                    "description": "YYYY-MM-DD. Defaults to today if omitted.",
                },
            },
        },
    },
    {
        "name": "log_note",
        "description": (
            "Log a free-form note or hypothesis. Use when the user expresses a belief, "
            "observation, or hypothesis ('I think magnesium is improving my HRV', "
            "'seems like stress tanks my sleep'). "
            'For hypotheses set attributes={"type":"hypothesis","cause":"...",'
            '"effect":"...","confidence":"low|medium|high"}.'
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "The note or hypothesis in the user's words.",
                },
                "attributes": {
                    "type": "object",
                    "description": (
                        "Optional structured data. For hypotheses: "
                        '{"type":"hypothesis","cause":"magnesium",'
                        '"effect":"hrv","confidence":"medium"}'
                    ),
                },
                "tags": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["text"],
        },
    },
    {
        "name": "list_recent_logs",
        "description": (
            "List recent health events, active protocols, and notes. "
            "Use to check for duplicates before logging, or to find protocol IDs for stop_protocol."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "Lookback window in days (default 14)",
                },
                "include": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["events", "protocols", "notes"],
                    },
                    "description": "Which log types to include (default all three)",
                },
            },
        },
    },
]

METRIC_MODEL_MAP = {
    "steps": (Steps, "total_steps"),
    "sleep": (Sleep, "total_sleep_minutes"),
    "heart_rate": (HeartRate, "resting_hr"),
    "hrv": (HRV, "hrv_avg"),
    "weight": (Weight, "weight_kg"),
    "energy": (Energy, "active_energy"),
}


def execute_tool(user_id: int, tool_name: str, tool_input: dict) -> dict:
    handlers = {
        "query_health_data": _handle_query_health_data,
        "get_predictions": _handle_get_predictions,
        "compare_periods": _handle_compare_periods,
        "log_event": _handle_log_event,
        "log_protocol": _handle_log_protocol,
        "stop_protocol": _handle_stop_protocol,
        "log_note": _handle_log_note,
        "list_recent_logs": _handle_list_recent_logs,
    }
    handler = handlers.get(tool_name)
    if not handler:
        return {"error": f"Unknown tool: {tool_name}"}
    return handler(user_id, tool_input)


def _handle_query_health_data(user_id: int, params: dict) -> dict:
    metric = params["metric"]
    start = date.fromisoformat(params["start_date"])
    end = date.fromisoformat(params["end_date"])

    if metric == "workouts":
        return _query_workouts(user_id, start, end)

    if metric == "strength":
        return _query_strength(user_id, start, end)

    model_info = METRIC_MODEL_MAP.get(metric)
    if not model_info:
        return {"error": f"Unknown metric: {metric}"}

    model_cls, value_col = model_info

    with get_db_session_context() as db:
        rows = (
            db.query(model_cls)
            .filter(
                model_cls.user_id == user_id,
                model_cls.date >= start,
                model_cls.date <= end,
            )
            .order_by(model_cls.date)
            .all()
        )

        data = []
        for r in rows:
            val = getattr(r, value_col, None)
            data.append({"date": str(r.date), "value": val})

    return {"metric": metric, "data": data, "count": len(data)}


def _query_workouts(user_id: int, start: date, end: date) -> dict:
    with get_db_session_context() as db:
        rows = (
            db.query(GarminActivity)
            .filter(
                GarminActivity.user_id == user_id,
                GarminActivity.date >= start,
                GarminActivity.date <= end,
            )
            .order_by(GarminActivity.date)
            .all()
        )

        data = []
        for r in rows:
            data.append(
                {
                    "date": str(r.date),
                    "type": r.activity_type,
                    "duration_min": (
                        round(r.duration_seconds / 60) if r.duration_seconds else None
                    ),
                    "calories": r.calories,
                    "avg_hr": r.avg_heart_rate,
                }
            )

    return {"metric": "workouts", "data": data, "count": len(data)}


def _query_strength(user_id: int, start: date, end: date) -> dict:
    with get_db_session_context() as db:
        rows = (
            db.query(
                WorkoutSet.date,
                WorkoutSet.exercise,
                func.count(WorkoutSet.id).label("sets"),
                func.max(WorkoutSet.weight_kg).label("max_weight"),
                func.sum(WorkoutSet.reps).label("total_reps"),
                func.max(WorkoutSet.rpe).label("max_rpe"),
            )
            .filter(
                WorkoutSet.user_id == user_id,
                WorkoutSet.date >= start,
                WorkoutSet.date <= end,
            )
            .group_by(WorkoutSet.date, WorkoutSet.exercise)
            .order_by(WorkoutSet.date, WorkoutSet.exercise)
            .all()
        )

        data = []
        for r in rows:
            data.append(
                {
                    "date": str(r.date),
                    "exercise": r.exercise,
                    "sets": r.sets,
                    "max_weight_kg": float(r.max_weight) if r.max_weight else None,
                    "total_reps": r.total_reps,
                    "max_rpe": float(r.max_rpe) if r.max_rpe else None,
                }
            )

    return {"metric": "strength", "data": data, "count": len(data)}


def _handle_get_predictions(user_id: int, params: dict) -> dict:
    metric = params["metric"]

    with get_db_session_context() as db:
        query = db.query(Prediction).filter(
            Prediction.user_id == user_id,
            Prediction.metric == metric,
            Prediction.target_date >= local_today(),
        )

        if "horizon_days" in params:
            query = query.filter(Prediction.horizon_days == params["horizon_days"])

        rows = query.order_by(Prediction.target_date).all()

        data = [
            {
                "target_date": str(r.target_date),
                "horizon_days": r.horizon_days,
                "p10": r.p10,
                "p50": r.p50,
                "p90": r.p90,
            }
            for r in rows
        ]

    return {"metric": metric, "predictions": data}


def _handle_compare_periods(user_id: int, params: dict) -> dict:
    metric = params["metric"]
    model_info = METRIC_MODEL_MAP.get(metric)
    if not model_info:
        return {"error": f"Unknown metric: {metric}"}

    model_cls, value_col = model_info

    def _avg_for_period(db: Session, start: date, end: date) -> float | None:
        result = (
            db.query(func.avg(getattr(model_cls, value_col)))
            .filter(
                model_cls.user_id == user_id,
                model_cls.date >= start,
                model_cls.date <= end,
            )
            .scalar()
        )
        return round(float(result), 2) if result else None

    with get_db_session_context() as db:
        a_start = date.fromisoformat(params["period_a_start"])
        a_end = date.fromisoformat(params["period_a_end"])
        b_start = date.fromisoformat(params["period_b_start"])
        b_end = date.fromisoformat(params["period_b_end"])

        avg_a = _avg_for_period(db, a_start, a_end)
        avg_b = _avg_for_period(db, b_start, b_end)

    change = None
    if avg_a and avg_b:
        change = round(((avg_b - avg_a) / avg_a) * 100, 1)

    return {
        "metric": metric,
        "period_a": {"start": str(a_start), "end": str(a_end), "avg": avg_a},
        "period_b": {"start": str(b_start), "end": str(b_end), "avg": avg_b},
        "change_pct": change,
    }


def _parse_ts(ts_str: str | None, default: datetime | None = None) -> datetime | None:
    if not ts_str:
        return default
    try:
        dt = datetime.fromisoformat(ts_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt
    except ValueError:
        try:
            d = parse_iso_date(ts_str)
            return datetime(d.year, d.month, d.day, tzinfo=UTC)
        except ValueError:
            return default


def _handle_log_event(user_id: int, params: dict) -> dict:
    name = (params.get("name") or "").strip()
    domain = params.get("domain")
    if not name:
        return {"error": "name is required"}
    if domain not in HEALTH_EVENT_DOMAINS:
        return {"error": f"domain must be one of {HEALTH_EVENT_DOMAINS}"}

    now_utc = datetime.now(UTC)
    start_ts = _parse_ts(params.get("start_ts"), default=now_utc) or now_utc
    end_ts = _parse_ts(params.get("end_ts"))

    if end_ts is not None and end_ts <= start_ts:
        return {"error": "end_ts must be after start_ts"}

    with get_db_session_context() as db:
        event = HealthEvent(
            user_id=user_id,
            domain=domain,
            name=name,
            start_ts=start_ts,
            end_ts=end_ts,
            dosage=params.get("dosage") or None,
            notes=params.get("notes") or None,
            attributes=params.get("attributes") or {},
            tags=params.get("tags") or [],
            protocol_id=params.get("protocol_id"),
        )
        db.add(event)
        db.flush()
        return {
            "status": "logged",
            "id": event.id,
            "name": event.name,
            "domain": event.domain,
            "start_ts": event.start_ts.isoformat(),
            "end_ts": event.end_ts.isoformat() if event.end_ts else None,
            "type": "point" if event.end_ts is None else "duration",
        }


def _handle_log_protocol(user_id: int, params: dict) -> dict:
    name = (params.get("name") or "").strip()
    domain = params.get("domain")
    if not name:
        return {"error": "name is required"}
    if domain not in PROTOCOL_DOMAINS:
        return {"error": f"domain must be one of {PROTOCOL_DOMAINS}"}

    start_date_str = params.get("start_date")
    try:
        start_date = parse_iso_date(start_date_str) if start_date_str else local_today()
    except ValueError:
        return {"error": f"invalid start_date: {start_date_str}"}

    with get_db_session_context() as db:
        existing = db.scalars(
            select(Protocol).filter(
                Protocol.user_id == user_id,
                Protocol.name == name,
                Protocol.end_date.is_(None),
            )
        ).first()
        if existing:
            return {
                "status": "already_active",
                "id": existing.id,
                "name": existing.name,
                "domain": existing.domain,
                "start_date": str(existing.start_date),
            }

        protocol = Protocol(
            user_id=user_id,
            name=name,
            domain=domain,
            start_date=start_date,
            dosage=params.get("dosage") or None,
            frequency=params.get("frequency") or None,
            notes=params.get("notes") or None,
            tags=params.get("tags") or [],
        )
        db.add(protocol)
        db.flush()
        return {
            "status": "started",
            "id": protocol.id,
            "name": protocol.name,
            "domain": protocol.domain,
            "start_date": str(protocol.start_date),
        }


def _handle_stop_protocol(user_id: int, params: dict) -> dict:
    protocol_id = params.get("protocol_id")
    name = (params.get("name") or "").strip()
    end_date_str = params.get("end_date")

    try:
        end_date = parse_iso_date(end_date_str) if end_date_str else local_today()
    except ValueError:
        return {"error": f"invalid end_date: {end_date_str}"}

    with get_db_session_context() as db:
        if protocol_id:
            row = db.scalars(
                select(Protocol).filter_by(id=protocol_id, user_id=user_id)
            ).first()
        elif name:
            row = db.scalars(
                select(Protocol).filter(
                    Protocol.user_id == user_id,
                    Protocol.name.ilike(f"%{name}%"),
                    Protocol.end_date.is_(None),
                )
            ).first()
        else:
            return {"error": "provide protocol_id or name"}

        if not row:
            return {"error": "active protocol not found"}

        row.end_date = end_date
        db.flush()
        return {
            "status": "stopped",
            "id": row.id,
            "name": row.name,
            "end_date": str(end_date),
        }


def _handle_log_note(user_id: int, params: dict) -> dict:
    text = (params.get("text") or "").strip()
    if not text:
        return {"error": "text is required"}

    with get_db_session_context() as db:
        note = HealthNote(
            user_id=user_id,
            text=text,
            attributes=params.get("attributes") or {},
            tags=params.get("tags") or [],
        )
        db.add(note)
        db.flush()
        return {
            "status": "noted",
            "id": note.id,
            "text": note.text[:100],
        }


def _handle_list_recent_logs(user_id: int, params: dict) -> dict:
    days = int(params.get("days", 14))
    include = set(params.get("include") or ["events", "protocols", "notes"])
    cutoff = local_today() - timedelta(days=days)
    cutoff_dt = datetime(cutoff.year, cutoff.month, cutoff.day, tzinfo=UTC)

    result: dict = {}

    with get_db_session_context() as db:
        if "events" in include:
            events = db.scalars(
                select(HealthEvent)
                .filter(
                    HealthEvent.user_id == user_id,
                    HealthEvent.start_ts >= cutoff_dt,
                )
                .order_by(HealthEvent.start_ts.desc())
            ).all()
            result["events"] = [
                {
                    "id": e.id,
                    "name": e.name,
                    "domain": e.domain,
                    "start_ts": e.start_ts.isoformat(),
                    "end_ts": e.end_ts.isoformat() if e.end_ts else None,
                    "dosage": e.dosage,
                    "type": "point" if e.end_ts is None else "duration",
                    "tags": e.tags,
                }
                for e in events
            ]

        if "protocols" in include:
            protocols = db.scalars(
                select(Protocol)
                .filter(
                    Protocol.user_id == user_id,
                    Protocol.start_date >= cutoff,
                )
                .order_by(Protocol.start_date.desc())
            ).all()
            active_protocols = db.scalars(
                select(Protocol).filter(
                    Protocol.user_id == user_id,
                    Protocol.end_date.is_(None),
                    Protocol.start_date < cutoff,
                )
            ).all()
            all_protocols = list(protocols) + list(active_protocols)
            result["protocols"] = [
                {
                    "id": p.id,
                    "name": p.name,
                    "domain": p.domain,
                    "start_date": str(p.start_date),
                    "end_date": str(p.end_date) if p.end_date else None,
                    "dosage": p.dosage,
                    "frequency": p.frequency,
                    "active": p.end_date is None,
                    "tags": p.tags,
                }
                for p in all_protocols
            ]

        if "notes" in include:
            notes = db.scalars(
                select(HealthNote)
                .filter(
                    HealthNote.user_id == user_id,
                    HealthNote.created_at >= cutoff,
                )
                .order_by(HealthNote.created_at.desc())
            ).all()
            result["notes"] = [
                {
                    "id": n.id,
                    "text": n.text,
                    "attributes": n.attributes,
                    "tags": n.tags,
                    "created_at": n.created_at.isoformat(),
                }
                for n in notes
            ]

    return {"lookback_days": days, **result}
