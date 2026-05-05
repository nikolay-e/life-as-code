from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from analytics.date_utils import local_today
from database import get_db_session_context
from date_utils import parse_iso_date
from models import (
    HRV,
    BloodBiomarker,
    BowelMovement,
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
    SubjectiveRating,
    UserSettings,
    Vital,
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
                "intensity": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 10,
                    "description": (
                        "0-10 magnitude/severity. Use for symptoms (pain 7), "
                        "stress events (intensity 8), workouts (RPE-like). Optional."
                    ),
                },
                "valence": {
                    "type": "integer",
                    "minimum": -5,
                    "maximum": 5,
                    "description": (
                        "-5 to +5 affective valence: -5=very bad, 0=neutral, +5=very good. "
                        "Use for therapy/sauna ('felt great'), bad reaction to a substance, etc."
                    ),
                },
                "body_location": {
                    "type": "string",
                    "description": (
                        "Anatomical location for symptoms/pain in English: "
                        "'left knee', 'lower back', 'right shoulder', 'forehead'. Optional."
                    ),
                },
                "duration_min": {
                    "type": "integer",
                    "minimum": 0,
                    "description": (
                        "Duration in minutes. Useful when end_ts is unknown but duration was "
                        "stated ('40 min sauna', 'meditation 20 min'). Optional."
                    ),
                },
                "related_event_id": {
                    "type": "integer",
                    "description": (
                        "ID of a prior health_event this event relates to. "
                        "Use for cross-references like 'pain after the workout' (set to the "
                        "prior workout/training event's id)."
                    ),
                },
                "related_workout_set_id": {
                    "type": "integer",
                    "description": (
                        "ID of a workout_set this event relates to (e.g. 'knee pain after "
                        "squats set 3'). Use only if the user references a specific set."
                    ),
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
                "alcohol_g": {
                    "type": "number",
                    "description": (
                        "Pure ethanol grams. Standard glass of wine ~14g, "
                        "shot of spirit ~14g, 0.5L beer 5% ~20g. Set when user logs alcohol."
                    ),
                },
                "caffeine_mg": {
                    "type": "number",
                    "description": (
                        "Caffeine in mg. Espresso ~63mg, drip coffee 8oz ~96mg, "
                        "black tea ~47mg, energy drink ~80-160mg. Set when user logs caffeine."
                    ),
                },
                "water_ml": {
                    "type": "number",
                    "description": (
                        "Volume of plain water in ml. Use this for dedicated hydration logs "
                        "('500ml of water'). Other drinks should be logged with their own product."
                    ),
                },
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
    {
        "name": "log_vital",
        "description": (
            "Log a single vital measurement (BP, glucose, ketones, SpO2, temperature, "
            "manual resting HR, manual weight, body fat %). Multi-per-day allowed. "
            "Use this when the user shares a single numeric reading like '120/80', "
            "'glucose 5.4', 'утром давление 130/85', 'sat 97'. For BP send TWO calls: "
            "kind='bp_sys' value=130, kind='bp_dia' value=85."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "kind": {
                    "type": "string",
                    "enum": [
                        "bp_sys",
                        "bp_dia",
                        "spo2",
                        "glucose_mg_dl",
                        "glucose_mmol_l",
                        "ketones_mmol_l",
                        "temp_c",
                        "resting_hr_bpm",
                        "respiratory_rate",
                        "weight_kg",
                        "body_fat_pct",
                    ],
                },
                "value": {"type": "number"},
                "unit": {
                    "type": "string",
                    "description": "Optional explicit unit string for display. Defaults derived from `kind`.",
                },
                "measured_at": {
                    "type": "string",
                    "description": "ISO datetime or YYYY-MM-DD. Defaults to now if omitted.",
                },
                "source": {
                    "type": "string",
                    "description": "e.g. 'manual', 'cuff', 'cgm', 'oura'. Optional.",
                },
                "notes": {"type": "string"},
            },
            "required": ["kind", "value"],
        },
    },
    {
        "name": "log_subjective",
        "description": (
            "Log a subjective 1-10 self-rating (mood, energy, focus, anxiety, stress, "
            "libido, motivation, sleep_quality, soreness, pain). Use this for any "
            "user statement like 'настроение 7', 'энергия низкая', 'libido 3'. "
            "Map vague qualitative reports to integers (плохо=2, нормально=5, отлично=9)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "dimension": {
                    "type": "string",
                    "enum": [
                        "mood",
                        "energy",
                        "focus",
                        "anxiety",
                        "stress",
                        "libido",
                        "motivation",
                        "sleep_quality",
                        "soreness",
                        "pain",
                    ],
                },
                "score": {"type": "integer", "minimum": 1, "maximum": 10},
                "measured_at": {
                    "type": "string",
                    "description": "ISO datetime or YYYY-MM-DD. Defaults to now if omitted.",
                },
                "notes": {"type": "string"},
            },
            "required": ["dimension", "score"],
        },
    },
    {
        "name": "log_bowel_movement",
        "description": (
            "Log a bowel movement with Bristol scale (1=hard pellets, 4=normal, 7=watery). "
            "Use when user mentions stool, defecation, или фразы вроде 'сходил в туалет'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "occurred_at": {
                    "type": "string",
                    "description": "ISO datetime. Defaults to now if omitted.",
                },
                "bristol_scale": {"type": "integer", "minimum": 1, "maximum": 7},
                "urgency": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 5,
                    "description": "1=normal, 5=very urgent.",
                },
                "blood": {"type": "boolean"},
                "notes": {"type": "string"},
            },
        },
    },
    {
        "name": "log_blood_biomarker",
        "description": (
            "Log a blood/lab biomarker result (LDL, HDL, ApoB, fasting glucose, A1C, hsCRP, "
            "vitamin D, ferritin, etc.). Use when user shares lab results — "
            "'ApoB 78', 'A1C 5.2', 'витамин D 32'. UNIQUE on (date, marker_name)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "YYYY-MM-DD of the blood draw."},
                "marker_name": {
                    "type": "string",
                    "description": (
                        "Canonical English name: 'LDL-C', 'HDL-C', 'ApoB', 'Triglycerides', "
                        "'Glucose (fasting)', 'HbA1c', 'hsCRP', 'Vitamin D 25-OH', "
                        "'Ferritin', 'TSH', 'Free T3', 'Free T4', 'Cortisol AM', 'Testosterone Total'."
                    ),
                },
                "value": {"type": "number"},
                "unit": {
                    "type": "string",
                    "description": "e.g. 'mg/dL', 'mmol/L', 'nmol/L', 'µIU/mL', 'ng/mL'.",
                },
                "reference_range_low": {"type": "number"},
                "reference_range_high": {"type": "number"},
                "longevity_optimal_low": {"type": "number"},
                "longevity_optimal_high": {"type": "number"},
                "lab_name": {"type": "string"},
                "notes": {"type": "string"},
            },
            "required": ["date", "marker_name", "value"],
        },
    },
    {
        "name": "log_functional_test",
        "description": (
            "Log a functional fitness test result (VO2 max test, grip strength, "
            "DEXA scan derivatives, sit-and-reach, plank time, dead-hang time, etc.)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "YYYY-MM-DD."},
                "test_name": {"type": "string"},
                "value": {"type": "number"},
                "unit": {"type": "string"},
                "notes": {"type": "string"},
            },
            "required": ["date", "test_name", "value"],
        },
    },
    {
        "name": "delete_recent_log",
        "description": (
            "Delete a recent log row by table + id. Use when the user says "
            "'удали последнюю запись', 'это была ошибка'. If the user says 'last' "
            "without an id, first call list_recent_logs / get_food_log / search_logs to "
            "find the id, confirm with user, then call this."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "kind": {
                    "type": "string",
                    "enum": [
                        "event",
                        "protocol",
                        "note",
                        "food",
                        "vital",
                        "subjective",
                        "bowel",
                        "biomarker",
                        "functional_test",
                    ],
                },
                "id": {"type": "integer"},
            },
            "required": ["kind", "id"],
        },
    },
    {
        "name": "update_event",
        "description": (
            "Update an existing health_event by id. Use when the user corrects a prior log "
            "('not 100g but 200g', 'это было вчера а не сегодня'). Only fields you specify are changed; "
            "omit fields to leave them unchanged."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "event_id": {"type": "integer"},
                "name": {"type": "string"},
                "domain": {"type": "string", "enum": HEALTH_EVENT_DOMAINS},
                "start_ts": {"type": "string"},
                "end_ts": {"type": "string"},
                "dosage": {"type": "string"},
                "notes": {"type": "string"},
                "intensity": {"type": "integer", "minimum": 0, "maximum": 10},
                "valence": {"type": "integer", "minimum": -5, "maximum": 5},
                "body_location": {"type": "string"},
                "duration_min": {"type": "integer", "minimum": 0},
            },
            "required": ["event_id"],
        },
    },
    {
        "name": "update_food_log",
        "description": (
            "Update an existing food_log row by id. Use to correct quantity/macros/meal_type "
            "after a prior log ('I had 200g not 100g')."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "log_id": {"type": "integer"},
                "quantity_g": {"type": "number"},
                "calories": {"type": "number"},
                "protein_g": {"type": "number"},
                "fat_g": {"type": "number"},
                "carbs_g": {"type": "number"},
                "alcohol_g": {"type": "number"},
                "caffeine_mg": {"type": "number"},
                "water_ml": {"type": "number"},
                "meal_type": {
                    "type": "string",
                    "enum": ["breakfast", "lunch", "dinner", "snack", "other"],
                },
                "consumed_at": {"type": "string"},
                "description": {"type": "string"},
                "notes": {"type": "string"},
            },
            "required": ["log_id"],
        },
    },
    {
        "name": "search_logs",
        "description": (
            "Fuzzy full-text search across health_events, health_notes, food_products, "
            "and protocols using Postgres trigram. Use when user asks 'когда я последний раз "
            "ел Х', 'найди записи про колено', 'show me sauna entries'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Free-text query, Russian or English.",
                },
                "kinds": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["event", "note", "product", "protocol"],
                    },
                    "description": "Restrict scope. Defaults to all.",
                },
                "days": {
                    "type": "integer",
                    "description": "Lookback window in days (default 365).",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results across all kinds (default 20).",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "nutrition_lookup",
        "description": (
            "Look up nutrition info (kcal/protein/fat/carbs/fiber per 100g) for a food "
            "by name via OpenFoodFacts (multilingual incl. Russian). Use BEFORE log_food "
            "when the user names a food but no quantity/macros yet, or when you need to "
            "save_food_product. Always prefer this over web_search for nutrition data. "
            "If `save_top_match` is true, the best result is upserted to food_products and "
            "its id is returned for immediate use with log_food."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Free-text food name in Russian or English.",
                },
                "barcode": {
                    "type": "string",
                    "description": "Optional GTIN/EAN barcode for direct lookup.",
                },
                "save_top_match": {
                    "type": "boolean",
                    "description": (
                        "If true, the top match is saved as a FoodProduct (idempotent on "
                        "name+brand) and its id is returned. Defaults to false."
                    ),
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results to return (default 5).",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "log_weight_manual",
        "description": (
            "Log a manual weight measurement to the weight table (the same one Garmin "
            "syncs into). Use when the user weighs themselves manually and shares a number "
            "('сегодня 78.4кг'). One row per (user, date)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "YYYY-MM-DD. Defaults to today if omitted.",
                },
                "weight_kg": {"type": "number"},
                "body_fat_pct": {"type": "number"},
                "muscle_mass_kg": {"type": "number"},
                "notes": {"type": "string"},
            },
            "required": ["weight_kg"],
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
        "log_vital": _handle_log_vital,
        "log_subjective": _handle_log_subjective,
        "log_bowel_movement": _handle_log_bowel_movement,
        "log_blood_biomarker": _handle_log_blood_biomarker,
        "log_functional_test": _handle_log_functional_test,
        "delete_recent_log": _handle_delete_recent_log,
        "update_event": _handle_update_event,
        "update_food_log": _handle_update_food_log,
        "search_logs": _handle_search_logs,
        "log_weight_manual": _handle_log_weight_manual,
        "nutrition_lookup": _handle_nutrition_lookup,
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

    intensity = params.get("intensity")
    if intensity is not None and not 0 <= int(intensity) <= 10:
        return {"error": "intensity must be 0..10"}
    valence = params.get("valence")
    if valence is not None and not -5 <= int(valence) <= 5:
        return {"error": "valence must be -5..5"}
    duration_min = params.get("duration_min")
    if duration_min is not None and int(duration_min) < 0:
        return {"error": "duration_min must be >= 0"}

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
            intensity=int(intensity) if intensity is not None else None,
            valence=int(valence) if valence is not None else None,
            body_location=params.get("body_location") or None,
            duration_min=int(duration_min) if duration_min is not None else None,
            related_event_id=params.get("related_event_id"),
            related_workout_set_id=params.get("related_workout_set_id"),
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
            alcohol_g=params.get("alcohol_g"),
            caffeine_mg=params.get("caffeine_mg"),
            water_ml=params.get("water_ml"),
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
            "alcohol_g": log.alcohol_g,
            "caffeine_mg": log.caffeine_mg,
            "water_ml": log.water_ml,
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

    avg: dict | None = None
    if days:
        avg = {
            "calories": round(sum(float(d["calories"]) for d in days) / len(days), 1),
            "protein_g": round(sum(float(d["protein_g"]) for d in days) / len(days), 1),
            "fat_g": round(sum(float(d["fat_g"]) for d in days) / len(days), 1),
            "carbs_g": round(sum(float(d["carbs_g"]) for d in days) / len(days), 1),
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


VITAL_KIND_DEFAULT_UNITS = {
    "bp_sys": "mmHg",
    "bp_dia": "mmHg",
    "spo2": "%",
    "glucose_mg_dl": "mg/dL",
    "glucose_mmol_l": "mmol/L",
    "ketones_mmol_l": "mmol/L",
    "temp_c": "°C",
    "resting_hr_bpm": "bpm",
    "respiratory_rate": "br/min",
    "weight_kg": "kg",
    "body_fat_pct": "%",
}

VITAL_KINDS = tuple(VITAL_KIND_DEFAULT_UNITS.keys())

SUBJECTIVE_DIMENSIONS = (
    "mood",
    "energy",
    "focus",
    "anxiety",
    "stress",
    "libido",
    "motivation",
    "sleep_quality",
    "soreness",
    "pain",
)

DELETE_RECENT_LOG_KIND_TO_MODEL = {
    "event": HealthEvent,
    "protocol": Protocol,
    "note": HealthNote,
    "food": FoodLog,
    "vital": Vital,
    "subjective": SubjectiveRating,
    "bowel": BowelMovement,
    "biomarker": BloodBiomarker,
    "functional_test": FunctionalTest,
}


def _handle_log_vital(user_id: int, params: dict) -> dict:
    kind = params.get("kind")
    if kind not in VITAL_KINDS:
        return {"error": f"kind must be one of {list(VITAL_KINDS)}"}
    value = params.get("value")
    if value is None:
        return {"error": "value is required"}
    try:
        value_num = float(value)
    except (TypeError, ValueError):
        return {"error": f"invalid numeric value: {value!r}"}

    measured_at = _parse_ts(
        params.get("measured_at"), default=datetime.now(UTC)
    ) or datetime.now(UTC)

    with get_db_session_context() as db:
        vital = Vital(
            user_id=user_id,
            measured_at=measured_at,
            kind=kind,
            value=value_num,
            unit=params.get("unit") or VITAL_KIND_DEFAULT_UNITS.get(kind),
            source=params.get("source") or "manual",
            notes=params.get("notes") or None,
        )
        db.add(vital)
        db.flush()
        return {
            "status": "logged",
            "id": vital.id,
            "kind": vital.kind,
            "value": vital.value,
            "unit": vital.unit,
            "measured_at": vital.measured_at.isoformat(),
        }


def _handle_log_subjective(user_id: int, params: dict) -> dict:
    dimension = params.get("dimension")
    if dimension not in SUBJECTIVE_DIMENSIONS:
        return {"error": f"dimension must be one of {list(SUBJECTIVE_DIMENSIONS)}"}
    score = params.get("score")
    try:
        score_int = int(score)
    except (TypeError, ValueError):
        return {"error": f"score must be 1..10, got {score!r}"}
    if not 1 <= score_int <= 10:
        return {"error": "score must be 1..10"}

    measured_at = _parse_ts(
        params.get("measured_at"), default=datetime.now(UTC)
    ) or datetime.now(UTC)

    with get_db_session_context() as db:
        rating = SubjectiveRating(
            user_id=user_id,
            measured_at=measured_at,
            dimension=dimension,
            score=score_int,
            notes=params.get("notes") or None,
        )
        db.add(rating)
        db.flush()
        return {
            "status": "logged",
            "id": rating.id,
            "dimension": rating.dimension,
            "score": rating.score,
            "measured_at": rating.measured_at.isoformat(),
        }


def _handle_log_bowel_movement(user_id: int, params: dict) -> dict:
    occurred_at = _parse_ts(
        params.get("occurred_at"), default=datetime.now(UTC)
    ) or datetime.now(UTC)

    bristol = params.get("bristol_scale")
    if bristol is not None:
        try:
            bristol_int = int(bristol)
        except (TypeError, ValueError):
            return {"error": f"invalid bristol_scale: {bristol!r}"}
        if not 1 <= bristol_int <= 7:
            return {"error": "bristol_scale must be 1..7"}
    else:
        bristol_int = None

    urgency = params.get("urgency")
    if urgency is not None:
        try:
            urgency_int = int(urgency)
        except (TypeError, ValueError):
            return {"error": f"invalid urgency: {urgency!r}"}
        if not 1 <= urgency_int <= 5:
            return {"error": "urgency must be 1..5"}
    else:
        urgency_int = None

    with get_db_session_context() as db:
        bowel = BowelMovement(
            user_id=user_id,
            occurred_at=occurred_at,
            bristol_scale=bristol_int,
            urgency=urgency_int,
            blood=bool(params.get("blood")),
            notes=params.get("notes") or None,
        )
        db.add(bowel)
        db.flush()
        return {
            "status": "logged",
            "id": bowel.id,
            "occurred_at": bowel.occurred_at.isoformat(),
            "bristol_scale": bowel.bristol_scale,
        }


def _handle_log_blood_biomarker(user_id: int, params: dict) -> dict:
    date_str = params.get("date")
    marker_name = (params.get("marker_name") or "").strip()
    value = params.get("value")
    if not date_str:
        return {"error": "date is required (YYYY-MM-DD)"}
    if not marker_name:
        return {"error": "marker_name is required"}
    if value is None:
        return {"error": "value is required"}
    try:
        log_date = parse_iso_date(date_str)
    except ValueError:
        return {"error": f"invalid date: {date_str}"}
    try:
        value_num = float(value)
    except (TypeError, ValueError):
        return {"error": f"invalid numeric value: {value!r}"}

    with get_db_session_context() as db:
        existing = (
            db.query(BloodBiomarker)
            .filter_by(user_id=user_id, date=log_date, marker_name=marker_name)
            .first()
        )
        if existing:
            existing.value = value_num
            existing.unit = params.get("unit") or existing.unit
            existing.reference_range_low = params.get(
                "reference_range_low"
            ) or existing.reference_range_low
            existing.reference_range_high = params.get(
                "reference_range_high"
            ) or existing.reference_range_high
            existing.longevity_optimal_low = params.get(
                "longevity_optimal_low"
            ) or existing.longevity_optimal_low
            existing.longevity_optimal_high = params.get(
                "longevity_optimal_high"
            ) or existing.longevity_optimal_high
            existing.lab_name = params.get("lab_name") or existing.lab_name
            if params.get("notes"):
                existing.notes = params.get("notes")
            db.flush()
            return {
                "status": "updated",
                "id": existing.id,
                "marker_name": marker_name,
                "value": value_num,
                "date": str(log_date),
            }

        row = BloodBiomarker(
            user_id=user_id,
            date=log_date,
            marker_name=marker_name,
            value=value_num,
            unit=params.get("unit"),
            reference_range_low=params.get("reference_range_low"),
            reference_range_high=params.get("reference_range_high"),
            longevity_optimal_low=params.get("longevity_optimal_low"),
            longevity_optimal_high=params.get("longevity_optimal_high"),
            lab_name=params.get("lab_name"),
            notes=params.get("notes"),
        )
        db.add(row)
        db.flush()
        return {
            "status": "logged",
            "id": row.id,
            "marker_name": marker_name,
            "value": value_num,
            "date": str(log_date),
        }


def _handle_log_functional_test(user_id: int, params: dict) -> dict:
    date_str = params.get("date")
    test_name = (params.get("test_name") or "").strip()
    value = params.get("value")
    if not date_str or not test_name or value is None:
        return {"error": "date, test_name, value are required"}
    try:
        log_date = parse_iso_date(date_str)
    except ValueError:
        return {"error": f"invalid date: {date_str}"}
    try:
        value_num = float(value)
    except (TypeError, ValueError):
        return {"error": f"invalid numeric value: {value!r}"}

    with get_db_session_context() as db:
        row = FunctionalTest(
            user_id=user_id,
            date=log_date,
            test_name=test_name,
            value=value_num,
            unit=params.get("unit"),
            notes=params.get("notes"),
        )
        db.add(row)
        db.flush()
        return {
            "status": "logged",
            "id": row.id,
            "test_name": test_name,
            "value": value_num,
            "date": str(log_date),
        }


def _handle_log_weight_manual(user_id: int, params: dict) -> dict:
    weight_kg = params.get("weight_kg")
    if weight_kg is None:
        return {"error": "weight_kg is required"}
    try:
        weight_num = float(weight_kg)
    except (TypeError, ValueError):
        return {"error": f"invalid weight_kg: {weight_kg!r}"}

    date_str = params.get("date")
    try:
        log_date = parse_iso_date(date_str) if date_str else local_today()
    except ValueError:
        return {"error": f"invalid date: {date_str}"}

    with get_db_session_context() as db:
        existing = (
            db.query(Weight)
            .filter_by(user_id=user_id, date=log_date)
            .first()
        )
        if existing:
            existing.weight_kg = weight_num
            if params.get("body_fat_pct") is not None:
                existing.body_fat_pct = float(params.get("body_fat_pct"))
            if params.get("muscle_mass_kg") is not None:
                existing.muscle_mass_kg = float(params.get("muscle_mass_kg"))
            existing.source = "manual"
            db.flush()
            return {
                "status": "updated",
                "id": existing.id,
                "weight_kg": weight_num,
                "date": str(log_date),
            }
        row = Weight(
            user_id=user_id,
            date=log_date,
            source="manual",
            weight_kg=weight_num,
            body_fat_pct=(
                float(params.get("body_fat_pct"))
                if params.get("body_fat_pct") is not None
                else None
            ),
            muscle_mass_kg=(
                float(params.get("muscle_mass_kg"))
                if params.get("muscle_mass_kg") is not None
                else None
            ),
        )
        db.add(row)
        db.flush()
        return {
            "status": "logged",
            "id": row.id,
            "weight_kg": weight_num,
            "date": str(log_date),
        }


def _handle_delete_recent_log(user_id: int, params: dict) -> dict:
    kind = params.get("kind")
    log_id = params.get("id")
    model = DELETE_RECENT_LOG_KIND_TO_MODEL.get(kind or "")
    if model is None:
        return {
            "error": f"kind must be one of {list(DELETE_RECENT_LOG_KIND_TO_MODEL)}"
        }
    if not log_id:
        return {"error": "id is required"}

    with get_db_session_context() as db:
        row = (
            db.query(model)
            .filter(model.id == log_id, model.user_id == user_id)
            .first()
        )
        if not row:
            return {"error": f"{kind} {log_id} not found"}
        db.delete(row)
        return {"status": "deleted", "kind": kind, "id": log_id}


def _handle_update_event(user_id: int, params: dict) -> dict:
    event_id = params.get("event_id")
    if not event_id:
        return {"error": "event_id is required"}

    with get_db_session_context() as db:
        row = (
            db.query(HealthEvent)
            .filter(HealthEvent.id == event_id, HealthEvent.user_id == user_id)
            .first()
        )
        if not row:
            return {"error": f"event {event_id} not found"}

        if params.get("name"):
            row.name = params["name"].strip()
        if params.get("domain"):
            domain = params["domain"]
            if domain not in HEALTH_EVENT_DOMAINS:
                return {"error": f"domain must be one of {HEALTH_EVENT_DOMAINS}"}
            row.domain = domain
        if params.get("start_ts"):
            row.start_ts = _parse_ts(params["start_ts"]) or row.start_ts
        if "end_ts" in params:
            end_ts_raw = params.get("end_ts")
            row.end_ts = _parse_ts(end_ts_raw) if end_ts_raw else None
        if "dosage" in params:
            row.dosage = params.get("dosage") or None
        if "notes" in params:
            row.notes = params.get("notes") or None
        if "intensity" in params and params["intensity"] is not None:
            row.intensity = int(params["intensity"])
        if "valence" in params and params["valence"] is not None:
            row.valence = int(params["valence"])
        if "body_location" in params:
            row.body_location = params.get("body_location") or None
        if "duration_min" in params and params["duration_min"] is not None:
            row.duration_min = int(params["duration_min"])

        db.flush()
        return {
            "status": "updated",
            "id": row.id,
            "name": row.name,
            "domain": row.domain,
        }


def _handle_update_food_log(user_id: int, params: dict) -> dict:
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
            return {"error": f"food log {log_id} not found"}

        for field in (
            "quantity_g",
            "calories",
            "protein_g",
            "fat_g",
            "carbs_g",
            "alcohol_g",
            "caffeine_mg",
            "water_ml",
        ):
            if field in params and params[field] is not None:
                setattr(row, field, float(params[field]))

        if params.get("meal_type"):
            row.meal_type = params["meal_type"]
        if params.get("description"):
            row.description = params["description"]
        if params.get("notes"):
            row.notes = params["notes"]
        if params.get("consumed_at"):
            ts = _parse_ts(params["consumed_at"])
            if ts is not None:
                row.consumed_at = ts
                row.date = ts.date()

        db.flush()
        return {
            "status": "updated",
            "id": row.id,
            "date": str(row.date),
            "calories": row.calories,
        }


def _handle_search_logs(user_id: int, params: dict) -> dict:
    from sqlalchemy import literal, or_, text

    query_str = (params.get("query") or "").strip()
    if not query_str:
        return {"error": "query is required"}

    kinds = params.get("kinds") or ["event", "note", "product", "protocol"]
    days = int(params.get("days") or 365)
    limit = int(params.get("limit") or 20)
    cutoff = datetime.now(UTC) - timedelta(days=days)

    results: list[dict] = []

    with get_db_session_context() as db:
        if "event" in kinds:
            event_rows = (
                db.query(HealthEvent)
                .filter(HealthEvent.user_id == user_id)
                .filter(HealthEvent.start_ts >= cutoff)
                .filter(
                    or_(
                        HealthEvent.name.ilike(f"%{query_str}%"),
                        HealthEvent.notes.ilike(f"%{query_str}%"),
                        HealthEvent.body_location.ilike(f"%{query_str}%"),
                    )
                )
                .order_by(HealthEvent.start_ts.desc())
                .limit(limit)
                .all()
            )
            for r in event_rows:
                results.append(
                    {
                        "kind": "event",
                        "id": r.id,
                        "name": r.name,
                        "domain": r.domain,
                        "start_ts": r.start_ts.isoformat() if r.start_ts else None,
                        "notes": r.notes,
                        "body_location": r.body_location,
                        "intensity": r.intensity,
                    }
                )

        if "note" in kinds:
            note_rows = (
                db.query(HealthNote)
                .filter(HealthNote.user_id == user_id)
                .filter(HealthNote.created_at >= cutoff)
                .filter(HealthNote.text.ilike(f"%{query_str}%"))
                .order_by(HealthNote.created_at.desc())
                .limit(limit)
                .all()
            )
            for r in note_rows:
                results.append(
                    {
                        "kind": "note",
                        "id": r.id,
                        "text": r.text,
                        "created_at": (
                            r.created_at.isoformat() if r.created_at else None
                        ),
                    }
                )

        if "product" in kinds:
            product_rows = (
                db.query(FoodProduct)
                .filter(FoodProduct.user_id == user_id)
                .filter(FoodProduct.name.ilike(f"%{query_str}%"))
                .limit(limit)
                .all()
            )
            for r in product_rows:
                results.append(
                    {
                        "kind": "product",
                        "id": r.id,
                        "name": r.name,
                        "brand": r.brand,
                        "calories_per_100g": r.calories_per_100g,
                    }
                )

        if "protocol" in kinds:
            protocol_rows = (
                db.query(Protocol)
                .filter(Protocol.user_id == user_id)
                .filter(
                    or_(
                        Protocol.name.ilike(f"%{query_str}%"),
                        Protocol.notes.ilike(f"%{query_str}%"),
                    )
                )
                .order_by(Protocol.start_date.desc())
                .limit(limit)
                .all()
            )
            for r in protocol_rows:
                results.append(
                    {
                        "kind": "protocol",
                        "id": r.id,
                        "name": r.name,
                        "domain": r.domain,
                        "start_date": str(r.start_date) if r.start_date else None,
                        "end_date": str(r.end_date) if r.end_date else None,
                    }
                )

    _ = literal, text  # keep imports used regardless of branch
    results = results[:limit]
    return {"query": query_str, "count": len(results), "results": results}


def _handle_nutrition_lookup(user_id: int, params: dict) -> dict:
    from agent.nutrition import get_off_by_barcode, search_off

    query_str = (params.get("query") or "").strip()
    barcode = (params.get("barcode") or "").strip()
    limit = int(params.get("limit") or 5)
    save_top_match = bool(params.get("save_top_match"))

    if not query_str and not barcode:
        return {"error": "query or barcode is required"}

    matches: list[dict]
    if barcode:
        single = get_off_by_barcode(barcode)
        matches = [single] if single else []
    else:
        matches = search_off(query_str, lc="ru", page_size=limit)
        if not matches:
            matches = search_off(query_str, lc="en", page_size=limit)

    if not matches:
        return {"query": query_str or barcode, "count": 0, "matches": []}

    saved_id = None
    if save_top_match:
        top = matches[0]
        with get_db_session_context() as db:
            existing = (
                db.query(FoodProduct)
                .filter(
                    FoodProduct.user_id == user_id,
                    func.lower(FoodProduct.name) == (top.get("name") or "").lower(),
                )
                .first()
            )
            if existing:
                if top.get("calories_per_100g") is not None:
                    existing.calories_per_100g = top["calories_per_100g"]
                if top.get("protein_g_per_100g") is not None:
                    existing.protein_g_per_100g = top["protein_g_per_100g"]
                if top.get("fat_g_per_100g") is not None:
                    existing.fat_g_per_100g = top["fat_g_per_100g"]
                if top.get("carbs_g_per_100g") is not None:
                    existing.carbs_g_per_100g = top["carbs_g_per_100g"]
                if top.get("fiber_g_per_100g") is not None:
                    existing.fiber_g_per_100g = top["fiber_g_per_100g"]
                db.flush()
                saved_id = existing.id
            else:
                product = FoodProduct(
                    user_id=user_id,
                    name=top.get("name") or query_str,
                    brand=top.get("brand"),
                    calories_per_100g=top.get("calories_per_100g"),
                    protein_g_per_100g=top.get("protein_g_per_100g"),
                    fat_g_per_100g=top.get("fat_g_per_100g"),
                    carbs_g_per_100g=top.get("carbs_g_per_100g"),
                    fiber_g_per_100g=top.get("fiber_g_per_100g"),
                    notes=f"openfoodfacts:{top.get('code')}",
                )
                db.add(product)
                db.flush()
                saved_id = product.id

    return {
        "query": query_str or barcode,
        "count": len(matches),
        "matches": matches[:limit],
        "saved_product_id": saved_id,
    }
