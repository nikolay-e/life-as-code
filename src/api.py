import atexit
import math
import os
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from typing import Any

import pandas as pd
from flask import Blueprint, jsonify, request, session
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import func, select

from analytics import TrendMode
from analytics.pipeline import get_or_compute_snapshot
from data_loaders import (
    get_detailed_workout_data,
    get_garmin_activities_data,
    get_workout_volume_data,
    load_data_for_user,
)
from database import get_db_session_context
from date_utils import parse_date_string, utcnow
from enums import DataSource, SyncStatus
from errors import (
    APIError,
    ConflictError,
    InvalidCredentialsError,
    InvalidDateFormatError,
    NotAuthenticatedError,
    NotFoundError,
    ValidationError,
)
from limiter import limiter
from logging_config import get_logger
from models import (
    BloodBiomarker,
    DataSync,
    FunctionalTest,
    Intervention,
    LongevityGoal,
    User,
    UserSettings,
)
from pull_whoop_data import refresh_whoop_token_for_user
from routes import UserModel
from security import verify_password
from settings import get_settings
from sync_manager import is_sync_in_progress
from utils import get_user_credentials

api = Blueprint("api", __name__, url_prefix="/api")
logger = get_logger(__name__)
MSG_BODY_REQUIRED = "Request body is required"
_sync_executor = ThreadPoolExecutor(max_workers=4)
atexit.register(_sync_executor.shutdown, wait=False)


@api.errorhandler(APIError)
def handle_api_error(error: APIError):
    logger.error(
        "api_error",
        code=error.code.value,
        category=error.category.value,
        status=error.status,
        detail=error.detail,
        path=request.path,
    )
    return jsonify(error.to_problem_detail(instance=request.path)), error.status


@api.route("/version", methods=["GET"])
def get_version():
    s = get_settings()
    return jsonify(
        {
            "version": s.app_version,
            "buildDate": s.build_date,
            "commit": s.commit_short,
            "commitFull": s.vcs_ref,
        }
    )


@api.route("/auth/login", methods=["POST"])
@limiter.limit("10 per minute")
def api_login():
    data = request.get_json()
    if not data:
        raise ValidationError(MSG_BODY_REQUIRED)

    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        raise ValidationError("Username and password are required")

    try:
        with get_db_session_context() as db:
            user = db.scalars(select(User).filter_by(username=username)).first()
            if user and verify_password(password, user.password_hash):
                session.clear()
                user_model = UserModel(user.id, user.username)
                login_user(user_model)
                logger.info("login_success", username=username, user_id=user.id)
                return jsonify(
                    {
                        "user": {
                            "id": user.id,
                            "username": user.username,
                        }
                    }
                )
            logger.warning(
                "login_failed", username=username, reason="invalid_credentials"
            )
            raise InvalidCredentialsError()
    except APIError:
        raise
    except Exception:
        logger.exception("login_error", username=username)
        raise InvalidCredentialsError() from None


@api.route("/auth/logout", methods=["POST"])
@login_required
def api_logout():
    logout_user()
    return jsonify({"message": "Logged out"})


@api.route("/auth/me", methods=["GET"])
def api_me():
    if not current_user.is_authenticated:
        raise NotAuthenticatedError()
    return jsonify(
        {
            "user": {
                "id": current_user.id,
                "username": current_user.username,
            }
        }
    )


def sanitize_for_json(records: list[dict]) -> list[dict]:
    import math
    import numbers

    for record in records:
        for key, value in record.items():
            if isinstance(value, numbers.Real) and not isinstance(value, (int, bool)):
                if math.isnan(value) or math.isinf(value):
                    record[key] = None
    return records


@api.route("/analytics", methods=["GET"])
@login_required
def api_analytics():
    mode_str = request.args.get("mode", "recent")
    try:
        mode = TrendMode(mode_str)
    except ValueError:
        raise ValidationError(
            f"Invalid mode '{mode_str}'. Valid: recent, quarter, year, all",
            field="mode",
            provided_value=mode_str,
        ) from None

    with get_db_session_context() as db:
        analysis = get_or_compute_snapshot(db, current_user.id, mode=mode)
        return jsonify(analysis.model_dump())


@api.route("/ml/anomalies", methods=["GET"])
@login_required
def api_ml_anomalies():
    days = request.args.get("days", 14, type=int)
    with get_db_session_context() as db:
        from analytics.data_loader import load_ml_insights

        insights = load_ml_insights(db, current_user.id, anomaly_lookback_days=days)
        return jsonify(
            {
                "anomalies": [a.model_dump() for a in insights.ml_anomalies],
                "count": len(insights.ml_anomalies),
                "has_recent": insights.has_recent_ml_anomalies,
            }
        )


@api.route("/ml/forecasts", methods=["GET"])
@login_required
def api_ml_forecasts():
    metric = request.args.get("metric")
    horizon = request.args.get("horizon", 14, type=int)
    with get_db_session_context() as db:
        from analytics.data_loader import load_ml_insights

        insights = load_ml_insights(db, current_user.id)
        forecasts = [
            f for f in insights.forecasts if metric is None or f.metric == metric
        ]
        horizon_filtered = [
            {
                "metric": f.metric,
                "forecasts": [
                    p.model_dump() for p in f.forecasts if p.horizon_days <= horizon
                ],
            }
            for f in forecasts
        ]
        return jsonify(
            {
                "forecasts": horizon_filtered,
                "has_active": insights.has_active_forecasts,
            }
        )


def _parse_date_range(start_str: str | None, end_str: str | None) -> tuple[Any, Any]:
    if not start_str or not end_str:
        end = datetime.now().date()
        return end - timedelta(days=90), end
    try:
        return parse_date_string(start_str), parse_date_string(end_str)
    except ValueError:
        raise InvalidDateFormatError(f"{start_str} or {end_str}") from None


def _serialize_workouts_df(df) -> list[dict]:
    volume_df = get_workout_volume_data(df)
    if volume_df.empty:
        return []
    volume_df["date"] = volume_df["date"].astype(str)
    return sanitize_for_json(volume_df.to_dict(orient="records"))


def _serialize_generic_df(df) -> list[dict]:
    df["date"] = df["date"].astype(str)
    for col in df.select_dtypes(include=["datetime64[ns]"]).columns:
        df[col] = df[col].apply(lambda x: x.isoformat() if pd.notna(x) else None)
    return sanitize_for_json(df.to_dict(orient="records"))


@api.route("/data/range", methods=["GET"])
@login_required
def api_data_range():
    start_date, end_date = _parse_date_range(
        request.args.get("start_date"), request.args.get("end_date")
    )
    data = load_data_for_user(start_date, end_date, current_user.id)

    result = {}
    for key, df in data.items():
        if df.empty:
            result[key] = []
        elif key == "workouts":
            result[key] = _serialize_workouts_df(df)
        else:
            result[key] = _serialize_generic_df(df)

    return jsonify(result)


@api.route("/data/workouts/detailed", methods=["GET"])
@login_required
def api_workouts_detailed():
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    if not start_date or not end_date:
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=90)
    else:
        try:
            start_date = parse_date_string(start_date)
            end_date = parse_date_string(end_date)
        except ValueError:
            raise InvalidDateFormatError(f"{start_date} or {end_date}") from None

    result = get_detailed_workout_data(start_date, end_date, current_user.id)
    return jsonify(sanitize_for_json(result))


@api.route("/data/activities/garmin", methods=["GET"])
@login_required
def api_garmin_activities():
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    if not start_date or not end_date:
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=90)
    else:
        try:
            start_date = parse_date_string(start_date)
            end_date = parse_date_string(end_date)
        except ValueError:
            raise InvalidDateFormatError(f"{start_date} or {end_date}") from None

    result = get_garmin_activities_data(start_date, end_date, current_user.id)
    return jsonify(sanitize_for_json(result))


@api.route("/settings/thresholds", methods=["GET"])
@login_required
def api_get_thresholds():
    with get_db_session_context() as db:
        settings = db.scalars(
            select(UserSettings).filter_by(user_id=current_user.id)
        ).first()

        if not settings:
            return jsonify(
                {
                    "hrv_good_threshold": 45,
                    "hrv_moderate_threshold": 35,
                    "deep_sleep_good_threshold": 90,
                    "deep_sleep_moderate_threshold": 60,
                    "total_sleep_good_threshold": 7.5,
                    "total_sleep_moderate_threshold": 6.5,
                    "training_high_volume_threshold": 5000,
                }
            )

        return jsonify(
            {
                "hrv_good_threshold": settings.hrv_good_threshold,
                "hrv_moderate_threshold": settings.hrv_moderate_threshold,
                "deep_sleep_good_threshold": settings.deep_sleep_good_threshold,
                "deep_sleep_moderate_threshold": settings.deep_sleep_moderate_threshold,
                "total_sleep_good_threshold": settings.total_sleep_good_threshold,
                "total_sleep_moderate_threshold": settings.total_sleep_moderate_threshold,
                "training_high_volume_threshold": settings.training_high_volume_threshold,
            }
        )


def _validate_threshold(
    value: Any, name: str, min_val: float, max_val: float
) -> float | None:
    if value is None:
        return None
    try:
        num_val = float(value)
        if not (min_val <= num_val <= max_val):
            raise ValidationError(
                f"{name} must be between {min_val} and {max_val}",
                field=name,
                provided_value=value,
            )
        return num_val
    except (TypeError, ValueError):
        raise ValidationError(
            f"{name} must be a number", field=name, provided_value=value
        ) from None


@api.route("/settings/thresholds", methods=["PUT"])
@login_required
def api_save_thresholds():
    data = request.get_json()
    if not data:
        raise ValidationError(MSG_BODY_REQUIRED)

    validated = {}

    int_thresholds = {
        "hrv_good_threshold": (0, 500),
        "hrv_moderate_threshold": (0, 500),
        "deep_sleep_good_threshold": (0, 500),
        "deep_sleep_moderate_threshold": (0, 500),
        "training_high_volume_threshold": (0, 100000),
    }
    for key, (min_val, max_val) in int_thresholds.items():
        if key in data and data[key] is not None:
            result = _validate_threshold(data[key], key, min_val, max_val)
            if result is not None:
                validated[key] = int(result)

    float_thresholds = {
        "total_sleep_good_threshold": (0, 24),
        "total_sleep_moderate_threshold": (0, 24),
    }
    for key, (min_val, max_val) in float_thresholds.items():
        if key in data and data[key] is not None:
            validated[key] = _validate_threshold(data[key], key, min_val, max_val)

    with get_db_session_context() as db:
        settings = db.scalars(
            select(UserSettings).filter_by(user_id=current_user.id)
        ).first()

        if not settings:
            settings = UserSettings(user_id=current_user.id)
            db.add(settings)

        for key, value in validated.items():
            setattr(settings, key, value)

        db.commit()

        return jsonify(
            {
                "hrv_good_threshold": settings.hrv_good_threshold,
                "hrv_moderate_threshold": settings.hrv_moderate_threshold,
                "deep_sleep_good_threshold": settings.deep_sleep_good_threshold,
                "deep_sleep_moderate_threshold": settings.deep_sleep_moderate_threshold,
                "total_sleep_good_threshold": settings.total_sleep_good_threshold,
                "total_sleep_moderate_threshold": settings.total_sleep_moderate_threshold,
                "training_high_volume_threshold": settings.training_high_volume_threshold,
            }
        )


def _check_whoop_token_status(creds) -> tuple[bool, bool]:
    if creds is None:
        return False, False
    whoop_has_token = bool(creds.encrypted_whoop_access_token)
    if not whoop_has_token:
        return False, False
    whoop_token_expired = False
    if creds.whoop_token_expires_at:
        expires_at = creds.whoop_token_expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        whoop_token_expired = expires_at < datetime.now(UTC)
    return whoop_has_token, whoop_token_expired


def _maybe_refresh_whoop_token(creds, user_id: int, token_expired: bool) -> bool:
    if not token_expired or creds is None or not creds.encrypted_whoop_refresh_token:
        return token_expired
    logger.info("whoop_token_expired_refreshing", user_id=user_id)
    if refresh_whoop_token_for_user(user_id):
        logger.info("whoop_token_refreshed_proactively", user_id=user_id)
        return False
    return token_expired


@api.route("/settings/credentials", methods=["GET"])
@login_required
def api_get_credentials():
    creds = get_user_credentials(current_user.id)
    whoop_client_id = os.getenv("WHOOP_CLIENT_ID")
    whoop_auth_url = "/whoop/authorize" if whoop_client_id else None

    whoop_has_token, whoop_token_expired = _check_whoop_token_status(creds)
    whoop_token_expired = _maybe_refresh_whoop_token(
        creds, current_user.id, whoop_token_expired
    )

    return jsonify(
        {
            "garmin_configured": bool(
                creds and creds.garmin_email and creds.encrypted_garmin_password
            ),
            "hevy_configured": bool(creds and creds.encrypted_hevy_api_key),
            "whoop_configured": whoop_has_token and not whoop_token_expired,
            "whoop_token_expired": whoop_token_expired,
            "whoop_auth_url": whoop_auth_url,
            "message": "Credentials are managed through environment variables",
        }
    )


@api.route("/sync/status", methods=["GET"])
@login_required
def api_sync_status():
    limit = max(1, min(request.args.get("limit", 50, type=int), 200))
    offset = max(0, request.args.get("offset", 0, type=int))
    with get_db_session_context() as db:
        base_query = (
            select(DataSync)
            .filter_by(user_id=current_user.id)
            .order_by(DataSync.last_sync_timestamp.desc())
        )
        total = db.scalar(select(func.count()).select_from(base_query.subquery()))
        syncs = db.scalars(base_query.offset(offset).limit(limit)).all()

        return jsonify(
            {
                "items": [
                    {
                        "source": s.source,
                        "data_type": s.data_type,
                        "last_sync_date": (
                            s.last_sync_date.isoformat() if s.last_sync_date else None
                        ),
                        "last_sync_timestamp": (
                            s.last_sync_timestamp.isoformat() + "Z"
                            if s.last_sync_timestamp
                            else None
                        ),
                        "records_synced": s.records_synced,
                        "status": s.status,
                        "error_message": s.error_message,
                    }
                    for s in syncs
                ],
                "total": total,
                "limit": limit,
                "offset": offset,
            }
        )


def _update_data_sync(
    user_id: int, source: str, result: dict[str, Any], success: bool
) -> None:
    try:
        with get_db_session_context() as db:
            existing_sync = db.scalars(
                select(DataSync).where(
                    DataSync.user_id == user_id,
                    DataSync.source == source,
                    DataSync.data_type == "all",
                )
            ).first()

            now = utcnow()
            records_synced = result.get("total_records_created", 0) + result.get(
                "total_records_updated", 0
            )
            status = SyncStatus.SUCCESS if success else SyncStatus.ERROR
            error_message = result.get("error") if not success else None

            if existing_sync:
                existing_sync.last_sync_timestamp = now
                existing_sync.last_sync_date = now.date()
                existing_sync.records_synced = records_synced
                existing_sync.status = status
                existing_sync.error_message = error_message
            else:
                new_sync = DataSync(
                    user_id=user_id,
                    source=source,
                    data_type="all",
                    last_sync_timestamp=now,
                    last_sync_date=now.date(),
                    records_synced=records_synced,
                    status=status,
                    error_message=error_message,
                )
                db.add(new_sync)
    except Exception as e:
        logger.error("data_sync_status_update_error", error=str(e))


def _run_two_phase_sync(
    user_id: int, sync_func: Callable[..., dict[str, Any] | None], source: str
) -> None:
    """Run quick 90-day sync, then trigger full historical sync in background."""
    try:
        logger.info(
            "sync_phase_started",
            source=source,
            user_id=user_id,
            phase="quick",
            days=90,
        )
        result: dict[str, Any] = sync_func(user_id, days=90, full_sync=False) or {}

        if result.get("success", False):
            logger.info(
                "sync_phase_completed",
                source=source,
                user_id=user_id,
                phase="quick",
                records_processed=result.get("total_records_processed", 0),
                records_created=result.get("total_records_created", 0),
                errors=result.get("total_errors", 0),
            )
            _update_data_sync(user_id, source, result, success=True)

            logger.info(
                "sync_phase_started",
                source=source,
                user_id=user_id,
                phase="full",
            )
            full_result: dict[str, Any] = sync_func(user_id, full_sync=True) or {}
            full_success = full_result.get("success", False)
            logger.info(
                "sync_phase_completed",
                source=source,
                user_id=user_id,
                phase="full",
                success=full_success,
                records_processed=full_result.get("total_records_processed", 0),
                records_created=full_result.get("total_records_created", 0),
                errors=full_result.get("total_errors", 0),
            )
            _update_data_sync(user_id, source, full_result, success=full_success)
        else:
            error_msg = result.get("error", "Unknown error")
            logger.error(
                "sync_phase_failed",
                source=source,
                user_id=user_id,
                phase="quick",
                error=error_msg,
                total_errors=result.get("total_errors", 0),
            )
            _update_data_sync(user_id, source, result, success=False)
    except Exception as e:
        logger.exception(
            "sync_unexpected_error",
            source=source,
            user_id=user_id,
            error_type=type(e).__name__,
            error=str(e),
        )
        _update_data_sync(
            user_id, source, {"success": False, "error": str(e)}, success=False
        )


def _handle_sync_request(
    source: DataSource,
    source_name: str,
    sync_func_getter: Callable[[], Callable[..., dict[str, Any] | None]],
):
    user_id = current_user.id

    if is_sync_in_progress(user_id, source):
        raise ConflictError(
            f"{source_name} sync already in progress",
            source=source_name.lower(),
        )

    days = request.args.get("days", type=int)
    full_sync = request.args.get("full", "").lower() == "true"

    def normalize_sync_result(result):
        if result is None:
            return {"success": True}
        if not isinstance(result, dict):
            return {"success": False, "error": "Unexpected sync result type"}
        return result

    def run_sync():
        sync_func = sync_func_getter()
        try:
            if full_sync:
                result = normalize_sync_result(sync_func(user_id, full_sync=True))
                _update_data_sync(
                    user_id, source_name.lower(), result, result.get("success", False)
                )
            elif days:
                result = normalize_sync_result(sync_func(user_id, days=days))
                _update_data_sync(
                    user_id, source_name.lower(), result, result.get("success", False)
                )
            else:
                _run_two_phase_sync(user_id, sync_func, source_name.lower())
        except Exception as e:
            _update_data_sync(
                user_id,
                source_name.lower(),
                {"success": False, "error": str(e)},
                False,
            )

    _sync_executor.submit(run_sync)

    if full_sync:
        sync_type = "full"
    elif days:
        sync_type = f"{days}-day"
    else:
        sync_type = "two-phase"
    return jsonify({"message": f"{source_name} {sync_type} sync started"})


@api.route("/sync/garmin", methods=["POST"])
@login_required
@limiter.limit("3000 per hour")
def api_sync_garmin():
    def get_sync_func():
        from pull_garmin_data import sync_garmin_data_for_user

        return sync_garmin_data_for_user

    return _handle_sync_request(DataSource.GARMIN, "Garmin", get_sync_func)


@api.route("/sync/hevy", methods=["POST"])
@login_required
@limiter.limit("3000 per hour")
def api_sync_hevy():
    def get_sync_func():
        from pull_hevy_data import sync_hevy_data_for_user

        return sync_hevy_data_for_user

    return _handle_sync_request(DataSource.HEVY, "Hevy", get_sync_func)


@api.route("/sync/whoop", methods=["POST"])
@login_required
@limiter.limit("3000 per hour")
def api_sync_whoop():
    def get_sync_func():
        from pull_whoop_data import sync_whoop_data_for_user

        return sync_whoop_data_for_user

    return _handle_sync_request(DataSource.WHOOP, "Whoop", get_sync_func)


@api.route("/settings/profile", methods=["GET"])
@login_required
def api_get_profile():
    with get_db_session_context() as db:
        settings = db.scalars(
            select(UserSettings).filter_by(user_id=current_user.id)
        ).first()
        return jsonify(
            {
                "birth_date": (
                    settings.birth_date.isoformat()
                    if settings and settings.birth_date
                    else None
                ),
                "gender": settings.gender if settings else None,
            }
        )


@api.route("/settings/profile", methods=["PUT"])
@login_required
def api_update_profile():
    data = request.get_json()
    if not data:
        raise ValidationError(MSG_BODY_REQUIRED)

    with get_db_session_context() as db:
        settings = db.scalars(
            select(UserSettings).filter_by(user_id=current_user.id)
        ).first()
        if not settings:
            settings = UserSettings(user_id=current_user.id)
            db.add(settings)

        if "birth_date" in data:
            if data["birth_date"]:
                try:
                    settings.birth_date = parse_date_string(data["birth_date"])
                except ValueError:
                    raise InvalidDateFormatError(data["birth_date"]) from None
            else:
                settings.birth_date = None

        if "gender" in data:
            if data["gender"] and data["gender"] not in ("male", "female"):
                raise ValidationError(
                    "Gender must be 'male' or 'female'",
                    field="gender",
                    provided_value=data["gender"],
                )
            settings.gender = data["gender"]

        db.commit()
        return jsonify(
            {
                "birth_date": (
                    settings.birth_date.isoformat() if settings.birth_date else None
                ),
                "gender": settings.gender,
            }
        )


VALID_INTERVENTION_CATEGORIES = {
    "supplement",
    "protocol",
    "medication",
    "lifestyle",
    "diet",
}


def _validate_finite_float(value: Any, field_name: str) -> float:
    try:
        num = float(value)
    except (ValueError, TypeError):
        raise ValidationError(
            f"{field_name} must be a number", field=field_name
        ) from None
    if math.isnan(num) or math.isinf(num):
        raise ValidationError(f"{field_name} must be a finite number", field=field_name)
    return num


def _serialize_model(obj, fields: list[str]) -> dict:
    result = {}
    for f in fields:
        val = getattr(obj, f)
        if hasattr(val, "isoformat"):
            result[f] = val.isoformat()
        else:
            result[f] = val
    return result


BIOMARKER_FIELDS = [
    "id",
    "date",
    "marker_name",
    "value",
    "unit",
    "reference_range_low",
    "reference_range_high",
    "longevity_optimal_low",
    "longevity_optimal_high",
    "lab_name",
    "notes",
]


@api.route("/longevity/biomarkers", methods=["GET"])
@login_required
def api_get_biomarkers():
    marker = request.args.get("marker")
    with get_db_session_context() as db:
        query = select(BloodBiomarker).filter_by(user_id=current_user.id)
        if marker:
            query = query.filter_by(marker_name=marker)
        query = query.order_by(BloodBiomarker.date.desc())
        rows = db.scalars(query).all()
        return jsonify([_serialize_model(r, BIOMARKER_FIELDS) for r in rows])


@api.route("/longevity/biomarkers", methods=["POST"])
@login_required
def api_create_biomarker():
    data = request.get_json()
    if not data:
        raise ValidationError(MSG_BODY_REQUIRED)

    for field in ("date", "marker_name", "unit"):
        if not data.get(field):
            raise ValidationError(f"{field} is required", field=field)
    if data.get("value") is None:
        raise ValidationError("value is required", field="value")

    try:
        parsed_date = parse_date_string(data["date"])
    except ValueError:
        raise InvalidDateFormatError(data["date"]) from None

    validated_value = _validate_finite_float(data["value"], "value")

    with get_db_session_context() as db:
        biomarker = BloodBiomarker(
            user_id=current_user.id,
            date=parsed_date,
            marker_name=data["marker_name"],
            value=validated_value,
            unit=data["unit"],
            reference_range_low=(
                _validate_finite_float(
                    data["reference_range_low"], "reference_range_low"
                )
                if data.get("reference_range_low") is not None
                else None
            ),
            reference_range_high=(
                _validate_finite_float(
                    data["reference_range_high"], "reference_range_high"
                )
                if data.get("reference_range_high") is not None
                else None
            ),
            longevity_optimal_low=(
                _validate_finite_float(
                    data["longevity_optimal_low"], "longevity_optimal_low"
                )
                if data.get("longevity_optimal_low") is not None
                else None
            ),
            longevity_optimal_high=(
                _validate_finite_float(
                    data["longevity_optimal_high"], "longevity_optimal_high"
                )
                if data.get("longevity_optimal_high") is not None
                else None
            ),
            lab_name=data.get("lab_name"),
            notes=data.get("notes"),
        )
        db.add(biomarker)
        db.commit()
        return jsonify(_serialize_model(biomarker, BIOMARKER_FIELDS)), 201


@api.route("/longevity/biomarkers/<int:biomarker_id>", methods=["DELETE"])
@login_required
def api_delete_biomarker(biomarker_id: int):
    with get_db_session_context() as db:
        row = db.scalars(
            select(BloodBiomarker).filter_by(id=biomarker_id, user_id=current_user.id)
        ).first()
        if not row:
            raise NotFoundError("Biomarker")
        db.delete(row)
        db.commit()
        return jsonify({"deleted": True})


INTERVENTION_FIELDS = [
    "id",
    "name",
    "category",
    "start_date",
    "end_date",
    "dosage",
    "frequency",
    "target_metrics",
    "notes",
    "active",
]


@api.route("/longevity/interventions", methods=["GET"])
@login_required
def api_get_interventions():
    active_only = request.args.get("active", "").lower() == "true"
    with get_db_session_context() as db:
        query = select(Intervention).filter_by(user_id=current_user.id)
        if active_only:
            query = query.filter_by(active=True)
        query = query.order_by(Intervention.start_date.desc())
        rows = db.scalars(query).all()
        return jsonify([_serialize_model(r, INTERVENTION_FIELDS) for r in rows])


@api.route("/longevity/interventions", methods=["POST"])
@login_required
def api_create_intervention():
    data = request.get_json()
    if not data:
        raise ValidationError(MSG_BODY_REQUIRED)

    for field in ("name", "category", "start_date"):
        if not data.get(field):
            raise ValidationError(f"{field} is required", field=field)

    if data["category"] not in VALID_INTERVENTION_CATEGORIES:
        raise ValidationError(
            f"category must be one of: {', '.join(sorted(VALID_INTERVENTION_CATEGORIES))}",
            field="category",
        )

    try:
        start = parse_date_string(data["start_date"])
    except ValueError:
        raise InvalidDateFormatError(data["start_date"]) from None

    end = None
    if data.get("end_date"):
        try:
            end = parse_date_string(data["end_date"])
        except ValueError:
            raise InvalidDateFormatError(data["end_date"]) from None

    with get_db_session_context() as db:
        intervention = Intervention(
            user_id=current_user.id,
            name=data["name"],
            category=data["category"],
            start_date=start,
            end_date=end,
            dosage=data.get("dosage"),
            frequency=data.get("frequency"),
            target_metrics=data.get("target_metrics"),
            notes=data.get("notes"),
            active=True,
        )
        db.add(intervention)
        db.commit()
        return jsonify(_serialize_model(intervention, INTERVENTION_FIELDS)), 201


def _parse_end_date(raw: Any):
    if not raw:
        return None
    try:
        return parse_date_string(raw)
    except ValueError:
        raise InvalidDateFormatError(raw) from None


def _apply_intervention_updates(row: Intervention, data: dict[str, Any]) -> None:
    if "category" in data and data["category"] not in VALID_INTERVENTION_CATEGORIES:
        raise ValidationError(
            f"category must be one of: {', '.join(sorted(VALID_INTERVENTION_CATEGORIES))}",
            field="category",
        )

    for field in ("name", "category", "dosage", "frequency", "notes"):
        if field in data:
            setattr(row, field, data[field])

    if "active" in data:
        row.active = bool(data["active"])

    if "end_date" in data:
        row.end_date = _parse_end_date(data["end_date"])

    if "target_metrics" in data:
        row.target_metrics = data["target_metrics"]


@api.route("/longevity/interventions/<int:intervention_id>", methods=["PUT"])
@login_required
def api_update_intervention(intervention_id: int):
    data = request.get_json()
    if not data:
        raise ValidationError(MSG_BODY_REQUIRED)

    with get_db_session_context() as db:
        row = db.scalars(
            select(Intervention).filter_by(id=intervention_id, user_id=current_user.id)
        ).first()
        if not row:
            raise NotFoundError("Intervention")

        _apply_intervention_updates(row, data)

        db.commit()
        return jsonify(_serialize_model(row, INTERVENTION_FIELDS))


@api.route("/longevity/interventions/<int:intervention_id>", methods=["DELETE"])
@login_required
def api_delete_intervention(intervention_id: int):
    with get_db_session_context() as db:
        row = db.scalars(
            select(Intervention).filter_by(id=intervention_id, user_id=current_user.id)
        ).first()
        if not row:
            raise NotFoundError("Intervention")
        db.delete(row)
        db.commit()
        return jsonify({"deleted": True})


FUNCTIONAL_TEST_FIELDS = ["id", "date", "test_name", "value", "unit", "notes"]


@api.route("/longevity/functional-tests", methods=["GET"])
@login_required
def api_get_functional_tests():
    test_name = request.args.get("test_name")
    with get_db_session_context() as db:
        query = select(FunctionalTest).filter_by(user_id=current_user.id)
        if test_name:
            query = query.filter_by(test_name=test_name)
        query = query.order_by(FunctionalTest.date.desc())
        rows = db.scalars(query).all()
        return jsonify([_serialize_model(r, FUNCTIONAL_TEST_FIELDS) for r in rows])


@api.route("/longevity/functional-tests", methods=["POST"])
@login_required
def api_create_functional_test():
    data = request.get_json()
    if not data:
        raise ValidationError(MSG_BODY_REQUIRED)

    for field in ("date", "test_name", "unit"):
        if not data.get(field):
            raise ValidationError(f"{field} is required", field=field)
    if data.get("value") is None:
        raise ValidationError("value is required", field="value")

    try:
        parsed_date = parse_date_string(data["date"])
    except ValueError:
        raise InvalidDateFormatError(data["date"]) from None

    validated_value = _validate_finite_float(data["value"], "value")

    with get_db_session_context() as db:
        test = FunctionalTest(
            user_id=current_user.id,
            date=parsed_date,
            test_name=data["test_name"],
            value=validated_value,
            unit=data["unit"],
            notes=data.get("notes"),
        )
        db.add(test)
        db.commit()
        return jsonify(_serialize_model(test, FUNCTIONAL_TEST_FIELDS)), 201


@api.route("/longevity/functional-tests/<int:test_id>", methods=["DELETE"])
@login_required
def api_delete_functional_test(test_id: int):
    with get_db_session_context() as db:
        row = db.scalars(
            select(FunctionalTest).filter_by(id=test_id, user_id=current_user.id)
        ).first()
        if not row:
            raise NotFoundError("Functional test")
        db.delete(row)
        db.commit()
        return jsonify({"deleted": True})


GOAL_FIELDS = [
    "id",
    "category",
    "description",
    "target_value",
    "current_value",
    "unit",
    "target_age",
]


@api.route("/longevity/goals", methods=["GET"])
@login_required
def api_get_goals():
    with get_db_session_context() as db:
        rows = db.scalars(
            select(LongevityGoal)
            .filter_by(user_id=current_user.id)
            .order_by(LongevityGoal.category)
        ).all()
        return jsonify([_serialize_model(r, GOAL_FIELDS) for r in rows])


@api.route("/longevity/goals", methods=["POST"])
@login_required
def api_create_goal():
    data = request.get_json()
    if not data:
        raise ValidationError(MSG_BODY_REQUIRED)

    for field in ("category", "description"):
        if not data.get(field):
            raise ValidationError(f"{field} is required", field=field)

    with get_db_session_context() as db:
        goal = LongevityGoal(
            user_id=current_user.id,
            category=data["category"],
            description=data["description"],
            target_value=(
                _validate_finite_float(data["target_value"], "target_value")
                if data.get("target_value") is not None
                else None
            ),
            current_value=(
                _validate_finite_float(data["current_value"], "current_value")
                if data.get("current_value") is not None
                else None
            ),
            unit=data.get("unit"),
            target_age=data.get("target_age"),
        )
        db.add(goal)
        db.commit()
        return jsonify(_serialize_model(goal, GOAL_FIELDS)), 201


@api.route("/longevity/goals/<int:goal_id>", methods=["PUT"])
@login_required
def api_update_goal(goal_id: int):
    data = request.get_json()
    if not data:
        raise ValidationError(MSG_BODY_REQUIRED)

    with get_db_session_context() as db:
        row = db.scalars(
            select(LongevityGoal).filter_by(id=goal_id, user_id=current_user.id)
        ).first()
        if not row:
            raise NotFoundError("Goal")

        for field in ("category", "description", "unit"):
            if field in data:
                setattr(row, field, data[field])

        for float_field in ("target_value", "current_value"):
            if float_field in data:
                setattr(
                    row,
                    float_field,
                    (
                        _validate_finite_float(data[float_field], float_field)
                        if data[float_field] is not None
                        else None
                    ),
                )

        if "target_age" in data:
            row.target_age = (
                int(data["target_age"]) if data["target_age"] is not None else None
            )

        db.commit()
        return jsonify(_serialize_model(row, GOAL_FIELDS))


@api.route("/longevity/goals/<int:goal_id>", methods=["DELETE"])
@login_required
def api_delete_goal(goal_id: int):
    with get_db_session_context() as db:
        row = db.scalars(
            select(LongevityGoal).filter_by(id=goal_id, user_id=current_user.id)
        ).first()
        if not row:
            raise NotFoundError("Goal")
        db.delete(row)
        db.commit()
        return jsonify({"deleted": True})
