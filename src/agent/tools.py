from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session

from analytics.date_utils import local_today
from database import get_db_session_context
from models import (
    HRV,
    Energy,
    GarminActivity,
    HeartRate,
    Prediction,
    Sleep,
    Steps,
    Weight,
    WorkoutSet,
)

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
