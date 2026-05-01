from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from analytics.date_utils import local_today
from database import get_db_session_context
from date_utils import parse_iso_date
from models import (
    HRV,
    Energy,
    GarminActivity,
    HeartRate,
    Intervention,
    Prediction,
    Sleep,
    Steps,
    Weight,
    WorkoutSet,
)

INTERVENTION_CATEGORIES = ["medication", "supplement", "protocol", "lifestyle", "diet"]

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
        "name": "log_intervention",
        "description": (
            "Log a lifestyle event, medication, supplement, protocol, or diet that the "
            "user mentions in the conversation. Use this proactively whenever the user "
            "tells you they took a supplement/medication, drank alcohol, was sick, "
            "fasted, did a sauna session, started a new diet, etc. The intervention "
            "becomes a marker on health charts for correlation analysis. "
            "If start_date is omitted, today is used."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": (
                        "Short canonical name (e.g. 'Magnesium Glycinate', 'Alcohol', "
                        "'Sauna', 'Illness — flu', 'Fasting 16h', 'Carnivore diet'). "
                        "Prefer English even if user wrote in Russian."
                    ),
                },
                "category": {
                    "type": "string",
                    "enum": INTERVENTION_CATEGORIES,
                },
                "start_date": {
                    "type": "string",
                    "description": "YYYY-MM-DD, defaults to today",
                },
                "end_date": {
                    "type": "string",
                    "description": "YYYY-MM-DD, optional (for one-day events like alcohol/sauna set same as start_date)",
                },
                "dosage": {
                    "type": "string",
                    "description": "e.g. '500mg', '2 capsules', '1 glass wine'. Optional.",
                },
                "frequency": {
                    "type": "string",
                    "description": "e.g. 'daily', 'twice daily', 'weekly'. Optional.",
                },
                "notes": {
                    "type": "string",
                    "description": "Brief context from the conversation. Optional.",
                },
            },
            "required": ["name", "category"],
        },
    },
    {
        "name": "list_recent_interventions",
        "description": (
            "List the user's recent interventions (last N days). Use to check if "
            "something is already logged before adding it, or to recall what the user "
            "took recently."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "Lookback window in days (default 14)",
                },
                "active_only": {
                    "type": "boolean",
                    "description": "Only return active interventions (default false)",
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
        "log_intervention": _handle_log_intervention,
        "list_recent_interventions": _handle_list_recent_interventions,
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


def _handle_log_intervention(user_id: int, params: dict) -> dict:
    name = (params.get("name") or "").strip()
    category = params.get("category")
    if not name:
        return {"error": "name is required"}
    if category not in INTERVENTION_CATEGORIES:
        return {"error": f"category must be one of {INTERVENTION_CATEGORIES}"}

    start_date_str = params.get("start_date")
    try:
        start_date = parse_iso_date(start_date_str) if start_date_str else local_today()
    except ValueError:
        return {"error": f"invalid start_date: {start_date_str}"}

    end_date = None
    end_date_str = params.get("end_date")
    if end_date_str:
        try:
            end_date = parse_iso_date(end_date_str)
        except ValueError:
            return {"error": f"invalid end_date: {end_date_str}"}

    with get_db_session_context() as db:
        existing = db.scalars(
            select(Intervention).filter_by(
                user_id=user_id,
                name=name,
                start_date=start_date,
                category=category,
            )
        ).first()
        if existing:
            return {
                "status": "already_logged",
                "id": existing.id,
                "name": existing.name,
                "category": existing.category,
                "start_date": str(existing.start_date),
            }

        intervention = Intervention(
            user_id=user_id,
            name=name,
            category=category,
            start_date=start_date,
            end_date=end_date,
            dosage=(params.get("dosage") or None),
            frequency=(params.get("frequency") or None),
            notes=(params.get("notes") or None),
            active=True,
        )
        db.add(intervention)
        db.flush()
        return {
            "status": "logged",
            "id": intervention.id,
            "name": intervention.name,
            "category": intervention.category,
            "start_date": str(intervention.start_date),
            "end_date": str(intervention.end_date) if intervention.end_date else None,
        }


def _handle_list_recent_interventions(user_id: int, params: dict) -> dict:
    days = int(params.get("days", 14))
    active_only = bool(params.get("active_only", False))
    cutoff = local_today() - __import__("datetime").timedelta(days=days)

    with get_db_session_context() as db:
        query = select(Intervention).filter(
            Intervention.user_id == user_id,
            Intervention.start_date >= cutoff,
        )
        if active_only:
            query = query.filter(Intervention.active.is_(True))
        rows = db.scalars(query.order_by(Intervention.start_date.desc())).all()

        data = [
            {
                "id": r.id,
                "name": r.name,
                "category": r.category,
                "start_date": str(r.start_date),
                "end_date": str(r.end_date) if r.end_date else None,
                "dosage": r.dosage,
                "frequency": r.frequency,
                "active": r.active,
            }
            for r in rows
        ]

    return {"interventions": data, "count": len(data), "lookback_days": days}
