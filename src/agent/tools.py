from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from analytics.date_utils import local_today
from database import get_db_session_context
from date_utils import parse_iso_date
from models import (
    HRV,
    BloodBiomarker,
    EightSleepSession,
    Energy,
    ExerciseTemplate,
    FoodLog,
    FoodProduct,
    FunctionalTest,
    GarminActivity,
    GarminRacePrediction,
    GarminTrainingStatus,
    HealthEvent,
    HealthNote,
    HeartRate,
    LongevityGoal,
    Prediction,
    Protocol,
    Sleep,
    Steps,
    Stress,
    UserSettings,
    Weight,
    WhoopCycle,
    WhoopRecovery,
    WhoopSleep,
    WhoopWorkout,
    WorkoutProgram,
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
                        "stress",
                        "whoop_recovery",
                        "whoop_sleep",
                        "whoop_workouts",
                        "whoop_cycle",
                        "eight_sleep",
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
                    "enum": [
                        "steps",
                        "sleep",
                        "heart_rate",
                        "hrv",
                        "weight",
                        "energy",
                        "stress",
                        "whoop_recovery",
                    ],
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
    {
        "name": "get_training_status",
        "description": (
            "Get Garmin training status metrics: VO2 max, fitness age, training load, "
            "training readiness, endurance score, and training status label."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "How many recent days to fetch (default 7)",
                },
            },
        },
    },
    {
        "name": "get_race_predictions",
        "description": "Get Garmin race time predictions (5K, 10K, half marathon, marathon) based on current fitness.",
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "Lookback window in days (default 30)",
                },
            },
        },
    },
    {
        "name": "get_blood_biomarkers",
        "description": (
            "Query blood biomarker lab results. Returns values with reference ranges "
            "and longevity-optimal ranges. Use for blood test history."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "marker_name": {
                    "type": "string",
                    "description": "Filter by marker name (e.g. 'Testosterone', 'HbA1c'). Optional.",
                },
                "days": {
                    "type": "integer",
                    "description": "Lookback window in days (default 365)",
                },
            },
        },
    },
    {
        "name": "get_functional_tests",
        "description": "Query functional fitness test results (e.g. VO2 max test, grip strength, flexibility scores).",
        "input_schema": {
            "type": "object",
            "properties": {
                "test_name": {
                    "type": "string",
                    "description": "Filter by test name. Optional.",
                },
                "days": {
                    "type": "integer",
                    "description": "Lookback window in days (default 365)",
                },
            },
        },
    },
    {
        "name": "get_longevity_goals",
        "description": "Get the user's longevity goals — target health metrics and milestones for extending healthy lifespan.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "get_training_program",
        "description": (
            "Get the user's workout program structure: program days, exercises, "
            "target sets/reps/RPE. Use to answer questions about the training plan."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "include_inactive": {
                    "type": "boolean",
                    "description": "Include archived programs (default false — active only)",
                },
            },
        },
    },
    {
        "name": "get_user_profile",
        "description": (
            "Get user profile and personalized thresholds: birth date / age, gender, "
            "height, HRV/sleep thresholds. Use for any calorie/BMR/TDEE calculation."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "search_exercises",
        "description": (
            "Search the user's Hevy exercise template catalog by name or muscle group. "
            "Use to find exercise definitions, equipment, primary/secondary muscles."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Substring match against exercise title (case-insensitive). Optional.",
                },
                "muscle_group": {
                    "type": "string",
                    "description": "Filter by primary muscle group. Optional.",
                },
                "limit": {"type": "integer", "description": "Max results (default 20)"},
            },
        },
    },
    {
        "name": "save_food_product",
        "description": (
            "Save or update a reusable food product with nutritional info per 100g/100ml. "
            "Use when the user tells you about a food they eat (e.g. 'this protein bar has 200kcal/40g'). "
            "Once saved, log_food can reference it by name for quick repeat logging."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Product name (canonical, e.g. 'Chicken breast')"},
                "brand": {"type": "string", "description": "Brand if relevant. Optional."},
                "calories_per_100g": {"type": "number"},
                "protein_g_per_100g": {"type": "number"},
                "fat_g_per_100g": {"type": "number"},
                "carbs_g_per_100g": {"type": "number"},
                "fiber_g_per_100g": {"type": "number"},
                "notes": {"type": "string"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "log_food",
        "description": (
            "Log a food intake. Two modes: "
            "(1) by product — set product_name (or product_id) + quantity_g, calories/macros are computed; "
            "(2) free-text — set description + manual calories/macros. "
            "Use this whenever the user mentions eating something. Logging is optional — not every day required."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "product_name": {"type": "string", "description": "Name of saved product. Fuzzy match."},
                "product_id": {"type": "integer", "description": "Exact product id (preferred over name)."},
                "quantity_g": {"type": "number", "description": "Grams/ml consumed (when using a product)."},
                "description": {"type": "string", "description": "Free-text description if no saved product."},
                "calories": {"type": "number"},
                "protein_g": {"type": "number"},
                "fat_g": {"type": "number"},
                "carbs_g": {"type": "number"},
                "meal_type": {
                    "type": "string",
                    "enum": ["breakfast", "lunch", "dinner", "snack", "other"],
                },
                "consumed_at": {
                    "type": "string",
                    "description": "ISO datetime or YYYY-MM-DD. Defaults to now if omitted.",
                },
                "notes": {"type": "string"},
            },
        },
    },
    {
        "name": "list_food_products",
        "description": "List saved food products. Optionally filter by name substring.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Substring match against product name."},
                "limit": {"type": "integer", "description": "Max results (default 50)"},
            },
        },
    },
    {
        "name": "get_food_log",
        "description": "Get food log entries for a date range. Returns each meal with macros.",
        "input_schema": {
            "type": "object",
            "properties": {
                "start_date": {"type": "string", "description": "YYYY-MM-DD"},
                "end_date": {"type": "string", "description": "YYYY-MM-DD"},
            },
            "required": ["start_date", "end_date"],
        },
    },
    {
        "name": "get_calorie_summary",
        "description": (
            "Aggregate daily calorie and macro totals over a date range. "
            "Returns per-day totals and the period average."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "start_date": {"type": "string", "description": "YYYY-MM-DD"},
                "end_date": {"type": "string", "description": "YYYY-MM-DD"},
            },
            "required": ["start_date", "end_date"],
        },
    },
    {
        "name": "delete_food_log",
        "description": "Delete a food log entry by id. Use when the user wants to undo or correct a logged meal.",
        "input_schema": {
            "type": "object",
            "properties": {
                "log_id": {"type": "integer"},
            },
            "required": ["log_id"],
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
    "stress": (Stress, "avg_stress"),
    "whoop_recovery": (WhoopRecovery, "recovery_score"),
    "whoop_sleep": (WhoopSleep, "sleep_performance_percentage"),
    "eight_sleep": (EightSleepSession, "score"),
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
        "get_training_status": _handle_get_training_status,
        "get_race_predictions": _handle_get_race_predictions,
        "get_blood_biomarkers": _handle_get_blood_biomarkers,
        "get_functional_tests": _handle_get_functional_tests,
        "get_longevity_goals": _handle_get_longevity_goals,
        "get_training_program": _handle_get_training_program,
        "get_user_profile": _handle_get_user_profile,
        "search_exercises": _handle_search_exercises,
        "save_food_product": _handle_save_food_product,
        "log_food": _handle_log_food,
        "list_food_products": _handle_list_food_products,
        "get_food_log": _handle_get_food_log,
        "get_calorie_summary": _handle_get_calorie_summary,
        "delete_food_log": _handle_delete_food_log,
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

    if metric == "whoop_workouts":
        return _query_whoop_workouts(user_id, start, end)

    if metric == "whoop_cycle":
        return _query_whoop_cycle(user_id, start, end)

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


def _query_whoop_workouts(user_id: int, start: date, end: date) -> dict:
    with get_db_session_context() as db:
        rows = (
            db.query(WhoopWorkout)
            .filter(
                WhoopWorkout.user_id == user_id,
                WhoopWorkout.date >= start,
                WhoopWorkout.date <= end,
            )
            .order_by(WhoopWorkout.date)
            .all()
        )
        data = [
            {
                "date": str(r.date),
                "sport": r.sport_name,
                "strain": r.strain,
                "avg_hr": r.avg_heart_rate,
                "max_hr": r.max_heart_rate,
                "kilojoules": r.kilojoules,
            }
            for r in rows
        ]
    return {"metric": "whoop_workouts", "data": data, "count": len(data)}


def _handle_get_training_status(user_id: int, params: dict) -> dict:
    days = int(params.get("days", 7))
    start = local_today() - timedelta(days=days)

    with get_db_session_context() as db:
        rows = (
            db.query(GarminTrainingStatus)
            .filter(
                GarminTrainingStatus.user_id == user_id,
                GarminTrainingStatus.date >= start,
            )
            .order_by(GarminTrainingStatus.date.desc())
            .all()
        )
        data = [
            {
                "date": str(r.date),
                "vo2_max": r.vo2_max,
                "vo2_max_precise": r.vo2_max_precise,
                "fitness_age": r.fitness_age,
                "training_status": r.training_status,
                "training_load_7_day": r.training_load_7_day,
                "acute_training_load": r.acute_training_load,
                "training_readiness_score": r.training_readiness_score,
                "endurance_score": r.endurance_score,
                "primary_training_effect": r.primary_training_effect,
                "anaerobic_training_effect": r.anaerobic_training_effect,
            }
            for r in rows
        ]
    return {"data": data, "count": len(data)}


def _handle_get_race_predictions(user_id: int, params: dict) -> dict:
    days = int(params.get("days", 30))
    start = local_today() - timedelta(days=days)

    def _fmt_time(seconds: int | None) -> str | None:
        if seconds is None:
            return None
        h, rem = divmod(seconds, 3600)
        m, s = divmod(rem, 60)
        return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

    with get_db_session_context() as db:
        rows = (
            db.query(GarminRacePrediction)
            .filter(
                GarminRacePrediction.user_id == user_id,
                GarminRacePrediction.date >= start,
            )
            .order_by(GarminRacePrediction.date.desc())
            .all()
        )
        data = [
            {
                "date": str(r.date),
                "5k": _fmt_time(r.prediction_5k_seconds),
                "10k": _fmt_time(r.prediction_10k_seconds),
                "half_marathon": _fmt_time(r.prediction_half_marathon_seconds),
                "marathon": _fmt_time(r.prediction_marathon_seconds),
                "vo2_max": r.vo2_max_value,
            }
            for r in rows
        ]
    return {"data": data, "count": len(data)}


def _handle_get_blood_biomarkers(user_id: int, params: dict) -> dict:
    days = int(params.get("days", 365))
    marker_name = params.get("marker_name")
    start = local_today() - timedelta(days=days)

    with get_db_session_context() as db:
        query = db.query(BloodBiomarker).filter(
            BloodBiomarker.user_id == user_id,
            BloodBiomarker.date >= start,
        )
        if marker_name:
            query = query.filter(BloodBiomarker.marker_name.ilike(f"%{marker_name}%"))
        rows = query.order_by(BloodBiomarker.date.desc(), BloodBiomarker.marker_name).all()
        data = [
            {
                "date": str(r.date),
                "marker": r.marker_name,
                "value": r.value,
                "unit": r.unit,
                "ref_low": r.reference_range_low,
                "ref_high": r.reference_range_high,
                "optimal_low": r.longevity_optimal_low,
                "optimal_high": r.longevity_optimal_high,
                "lab": r.lab_name,
                "notes": r.notes,
            }
            for r in rows
        ]
    return {"data": data, "count": len(data)}


def _handle_get_functional_tests(user_id: int, params: dict) -> dict:
    days = int(params.get("days", 365))
    test_name = params.get("test_name")
    start = local_today() - timedelta(days=days)

    with get_db_session_context() as db:
        query = db.query(FunctionalTest).filter(
            FunctionalTest.user_id == user_id,
            FunctionalTest.date >= start,
        )
        if test_name:
            query = query.filter(FunctionalTest.test_name.ilike(f"%{test_name}%"))
        rows = query.order_by(FunctionalTest.date.desc()).all()
        data = [
            {
                "date": str(r.date),
                "test": r.test_name,
                "value": r.value,
                "unit": r.unit,
                "notes": r.notes,
            }
            for r in rows
        ]
    return {"data": data, "count": len(data)}


def _handle_get_longevity_goals(user_id: int, params: dict) -> dict:
    with get_db_session_context() as db:
        rows = (
            db.query(LongevityGoal)
            .filter(LongevityGoal.user_id == user_id)
            .order_by(LongevityGoal.category)
            .all()
        )
        data = [
            {
                "category": r.category,
                "description": r.description,
                "target_value": r.target_value,
                "current_value": r.current_value,
                "unit": r.unit,
                "target_age": r.target_age,
            }
            for r in rows
        ]
    return {"goals": data, "count": len(data)}


def _handle_get_training_program(user_id: int, params: dict) -> dict:
    include_inactive = params.get("include_inactive", False)

    with get_db_session_context() as db:
        query = db.query(WorkoutProgram).filter(WorkoutProgram.user_id == user_id)
        if not include_inactive:
            query = query.filter(WorkoutProgram.is_active.is_(True))
        programs = query.order_by(WorkoutProgram.start_date.desc()).all()

        result = []
        for prog in programs:
            days_data = []
            for day in prog.days:
                exercises = [
                    {
                        "order": ex.exercise_order,
                        "title": ex.exercise_title,
                        "sets": ex.target_sets,
                        "reps": (
                            f"{ex.target_reps_min}-{ex.target_reps_max}"
                            if ex.target_reps_min and ex.target_reps_max
                            else ex.target_reps_min
                        ),
                        "rpe": (
                            f"{ex.target_rpe_min}-{ex.target_rpe_max}"
                            if ex.target_rpe_min and ex.target_rpe_max
                            else None
                        ),
                        "rest_sec": ex.rest_seconds,
                        "notes": ex.notes,
                    }
                    for ex in day.exercises
                ]
                days_data.append(
                    {
                        "order": day.day_order,
                        "name": day.name,
                        "focus": day.focus,
                        "exercises": exercises,
                    }
                )
            result.append(
                {
                    "id": prog.id,
                    "name": prog.name,
                    "goal": prog.goal,
                    "start_date": str(prog.start_date),
                    "end_date": str(prog.end_date) if prog.end_date else None,
                    "is_active": prog.is_active,
                    "days": days_data,
                }
            )
    return {"programs": result, "count": len(result)}


def _query_whoop_cycle(user_id: int, start: date, end: date) -> dict:
    with get_db_session_context() as db:
        rows = (
            db.query(WhoopCycle)
            .filter(
                WhoopCycle.user_id == user_id,
                WhoopCycle.date >= start,
                WhoopCycle.date <= end,
            )
            .order_by(WhoopCycle.date)
            .all()
        )
        data = [
            {
                "date": str(r.date),
                "strain": r.strain,
                "kilojoules": r.kilojoules,
                "avg_hr": r.avg_heart_rate,
                "max_hr": r.max_heart_rate,
            }
            for r in rows
        ]
    return {"metric": "whoop_cycle", "data": data, "count": len(data)}


def _handle_get_user_profile(user_id: int, params: dict) -> dict:
    with get_db_session_context() as db:
        row = (
            db.query(UserSettings)
            .filter(UserSettings.user_id == user_id)
            .first()
        )
        if not row:
            return {"profile": None}

        age = None
        if row.birth_date:
            today = local_today()
            age = today.year - row.birth_date.year - (
                (today.month, today.day) < (row.birth_date.month, row.birth_date.day)
            )

        return {
            "profile": {
                "birth_date": str(row.birth_date) if row.birth_date else None,
                "age": age,
                "gender": row.gender,
                "height_cm": row.height_cm,
                "thresholds": {
                    "hrv_good": row.hrv_good_threshold,
                    "hrv_moderate": row.hrv_moderate_threshold,
                    "deep_sleep_good_min": row.deep_sleep_good_threshold,
                    "deep_sleep_moderate_min": row.deep_sleep_moderate_threshold,
                    "total_sleep_good_h": row.total_sleep_good_threshold,
                    "total_sleep_moderate_h": row.total_sleep_moderate_threshold,
                    "training_high_volume_kg": row.training_high_volume_threshold,
                },
            }
        }


def _handle_search_exercises(user_id: int, params: dict) -> dict:
    query_str = (params.get("query") or "").strip()
    muscle_group = (params.get("muscle_group") or "").strip()
    limit = int(params.get("limit", 20))

    with get_db_session_context() as db:
        q = db.query(ExerciseTemplate).filter(ExerciseTemplate.user_id == user_id)
        if query_str:
            q = q.filter(ExerciseTemplate.title.ilike(f"%{query_str}%"))
        if muscle_group:
            q = q.filter(
                ExerciseTemplate.primary_muscle_group.ilike(f"%{muscle_group}%")
            )
        rows = q.order_by(ExerciseTemplate.title).limit(limit).all()
        data = [
            {
                "id": r.id,
                "hevy_template_id": r.hevy_template_id,
                "title": r.title,
                "type": r.exercise_type,
                "primary_muscle": r.primary_muscle_group,
                "secondary_muscles": r.secondary_muscle_groups,
                "equipment": r.equipment,
                "is_custom": r.is_custom,
            }
            for r in rows
        ]
    return {"exercises": data, "count": len(data)}


def _handle_save_food_product(user_id: int, params: dict) -> dict:
    name = (params.get("name") or "").strip()
    if not name:
        return {"error": "name is required"}
    brand = (params.get("brand") or "").strip() or None

    with get_db_session_context() as db:
        existing = (
            db.query(FoodProduct)
            .filter(
                FoodProduct.user_id == user_id,
                FoodProduct.name.ilike(name),
                FoodProduct.brand.is_(None) if brand is None else FoodProduct.brand.ilike(brand),
            )
            .first()
        )
        if existing:
            for field in (
                "calories_per_100g",
                "protein_g_per_100g",
                "fat_g_per_100g",
                "carbs_g_per_100g",
                "fiber_g_per_100g",
            ):
                if params.get(field) is not None:
                    setattr(existing, field, params[field])
            if params.get("notes") is not None:
                existing.notes = params["notes"]
            db.flush()
            product = existing
            status = "updated"
        else:
            product = FoodProduct(
                user_id=user_id,
                name=name,
                brand=brand,
                calories_per_100g=params.get("calories_per_100g"),
                protein_g_per_100g=params.get("protein_g_per_100g"),
                fat_g_per_100g=params.get("fat_g_per_100g"),
                carbs_g_per_100g=params.get("carbs_g_per_100g"),
                fiber_g_per_100g=params.get("fiber_g_per_100g"),
                notes=params.get("notes"),
            )
            db.add(product)
            db.flush()
            status = "created"

        return {
            "status": status,
            "id": product.id,
            "name": product.name,
            "brand": product.brand,
            "calories_per_100g": product.calories_per_100g,
        }


def _resolve_food_product(
    db: Session, user_id: int, product_id: int | None, product_name: str | None
) -> FoodProduct | None:
    if product_id:
        return (
            db.query(FoodProduct)
            .filter(FoodProduct.id == product_id, FoodProduct.user_id == user_id)
            .first()
        )
    if product_name:
        return (
            db.query(FoodProduct)
            .filter(
                FoodProduct.user_id == user_id,
                FoodProduct.name.ilike(f"%{product_name}%"),
            )
            .order_by(FoodProduct.name)
            .first()
        )
    return None


def _handle_log_food(user_id: int, params: dict) -> dict:
    consumed_at = _parse_ts(params.get("consumed_at"), default=datetime.now(UTC))
    if consumed_at is None:
        consumed_at = datetime.now(UTC)
    log_date = consumed_at.date()

    meal_type = params.get("meal_type")
    if meal_type and meal_type not in {
        "breakfast",
        "lunch",
        "dinner",
        "snack",
        "other",
    }:
        return {"error": f"invalid meal_type: {meal_type}"}

    quantity_g = params.get("quantity_g")
    description = (params.get("description") or "").strip() or None

    with get_db_session_context() as db:
        product = _resolve_food_product(
            db, user_id, params.get("product_id"), params.get("product_name")
        )

        calories = params.get("calories")
        protein_g = params.get("protein_g")
        fat_g = params.get("fat_g")
        carbs_g = params.get("carbs_g")

        if product and quantity_g is not None:
            factor = quantity_g / 100.0
            if calories is None and product.calories_per_100g is not None:
                calories = round(product.calories_per_100g * factor, 1)
            if protein_g is None and product.protein_g_per_100g is not None:
                protein_g = round(product.protein_g_per_100g * factor, 2)
            if fat_g is None and product.fat_g_per_100g is not None:
                fat_g = round(product.fat_g_per_100g * factor, 2)
            if carbs_g is None and product.carbs_g_per_100g is not None:
                carbs_g = round(product.carbs_g_per_100g * factor, 2)

        if not product and not description and calories is None:
            return {
                "error": "provide product_name/product_id, or description with macros"
            }

        log = FoodLog(
            user_id=user_id,
            consumed_at=consumed_at,
            date=log_date,
            meal_type=meal_type,
            product_id=product.id if product else None,
            quantity_g=quantity_g,
            description=description or (product.name if product else None),
            calories=calories,
            protein_g=protein_g,
            fat_g=fat_g,
            carbs_g=carbs_g,
            notes=params.get("notes"),
        )
        db.add(log)
        db.flush()

        return {
            "status": "logged",
            "id": log.id,
            "date": str(log.date),
            "consumed_at": log.consumed_at.isoformat(),
            "product": product.name if product else None,
            "quantity_g": quantity_g,
            "calories": calories,
            "protein_g": protein_g,
            "fat_g": fat_g,
            "carbs_g": carbs_g,
            "description": log.description,
        }


def _handle_list_food_products(user_id: int, params: dict) -> dict:
    query_str = (params.get("query") or "").strip()
    limit = int(params.get("limit", 50))

    with get_db_session_context() as db:
        q = db.query(FoodProduct).filter(FoodProduct.user_id == user_id)
        if query_str:
            q = q.filter(FoodProduct.name.ilike(f"%{query_str}%"))
        rows = q.order_by(FoodProduct.name).limit(limit).all()
        data = [
            {
                "id": r.id,
                "name": r.name,
                "brand": r.brand,
                "calories_per_100g": r.calories_per_100g,
                "protein_g_per_100g": r.protein_g_per_100g,
                "fat_g_per_100g": r.fat_g_per_100g,
                "carbs_g_per_100g": r.carbs_g_per_100g,
                "fiber_g_per_100g": r.fiber_g_per_100g,
                "notes": r.notes,
            }
            for r in rows
        ]
    return {"products": data, "count": len(data)}


def _handle_get_food_log(user_id: int, params: dict) -> dict:
    start = date.fromisoformat(params["start_date"])
    end = date.fromisoformat(params["end_date"])

    with get_db_session_context() as db:
        rows = (
            db.query(FoodLog)
            .filter(
                FoodLog.user_id == user_id,
                FoodLog.date >= start,
                FoodLog.date <= end,
            )
            .order_by(FoodLog.consumed_at)
            .all()
        )
        data = [
            {
                "id": r.id,
                "date": str(r.date),
                "consumed_at": r.consumed_at.isoformat(),
                "meal_type": r.meal_type,
                "product_id": r.product_id,
                "quantity_g": r.quantity_g,
                "description": r.description,
                "calories": r.calories,
                "protein_g": r.protein_g,
                "fat_g": r.fat_g,
                "carbs_g": r.carbs_g,
                "notes": r.notes,
            }
            for r in rows
        ]
    return {"entries": data, "count": len(data)}


def _handle_get_calorie_summary(user_id: int, params: dict) -> dict:
    start = date.fromisoformat(params["start_date"])
    end = date.fromisoformat(params["end_date"])

    with get_db_session_context() as db:
        rows = (
            db.query(
                FoodLog.date,
                func.coalesce(func.sum(FoodLog.calories), 0.0).label("calories"),
                func.coalesce(func.sum(FoodLog.protein_g), 0.0).label("protein_g"),
                func.coalesce(func.sum(FoodLog.fat_g), 0.0).label("fat_g"),
                func.coalesce(func.sum(FoodLog.carbs_g), 0.0).label("carbs_g"),
                func.count(FoodLog.id).label("entries"),
            )
            .filter(
                FoodLog.user_id == user_id,
                FoodLog.date >= start,
                FoodLog.date <= end,
            )
            .group_by(FoodLog.date)
            .order_by(FoodLog.date)
            .all()
        )

        days = [
            {
                "date": str(r.date),
                "calories": round(float(r.calories), 1),
                "protein_g": round(float(r.protein_g), 1),
                "fat_g": round(float(r.fat_g), 1),
                "carbs_g": round(float(r.carbs_g), 1),
                "entries": int(r.entries),
            }
            for r in rows
        ]

    avg = None
    if days:
        avg = {
            "calories": round(sum(d["calories"] for d in days) / len(days), 1),
            "protein_g": round(sum(d["protein_g"] for d in days) / len(days), 1),
            "fat_g": round(sum(d["fat_g"] for d in days) / len(days), 1),
            "carbs_g": round(sum(d["carbs_g"] for d in days) / len(days), 1),
            "logged_days": len(days),
        }

    return {"days": days, "average": avg}


def _handle_delete_food_log(user_id: int, params: dict) -> dict:
    log_id = params.get("log_id")
    if not log_id:
        return {"error": "log_id is required"}

    with get_db_session_context() as db:
        row = (
            db.query(FoodLog)
            .filter(FoodLog.id == log_id, FoodLog.user_id == user_id)
            .first()
        )
        if not row:
            return {"error": "food log entry not found"}
        db.delete(row)
        return {"status": "deleted", "id": log_id}
