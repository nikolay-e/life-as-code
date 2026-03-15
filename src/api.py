import os
import threading
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pandas as pd
from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import select

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
    ValidationError,
)
from limiter import limiter
from logging_config import get_logger
from models import DataSync, User, UserSettings
from pull_whoop_data import refresh_whoop_token_for_user
from routes import UserModel
from security import verify_password
from settings import get_settings
from sync_manager import is_sync_in_progress
from utils import get_user_credentials

api = Blueprint("api", __name__, url_prefix="/api")
logger = get_logger(__name__)


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
@limiter.limit("3000 per hour")
def api_login():
    data = request.get_json()
    if not data:
        raise ValidationError("Request body is required")

    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        raise ValidationError("Username and password are required")

    try:
        with get_db_session_context() as db:
            user = db.scalars(select(User).filter_by(username=username)).first()
            if user and verify_password(password, user.password_hash):
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
    except Exception as e:
        logger.exception("login_error", username=username, error=str(e))
        raise


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
        result = analysis.model_dump(exclude_none=True)
        if analysis.advanced_insights is not None:
            result["advanced_insights"] = analysis.advanced_insights.model_dump()
        return jsonify(result)


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


@api.route("/data/range", methods=["GET"])
@login_required
def api_data_range():
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

    data = load_data_for_user(start_date, end_date, current_user.id)

    result = {}
    for key, df in data.items():
        if df.empty:
            result[key] = []
        else:
            if key == "workouts":
                volume_df = get_workout_volume_data(df)
                if volume_df.empty:
                    result[key] = []
                else:
                    volume_df["date"] = volume_df["date"].astype(str)
                    result[key] = sanitize_for_json(volume_df.to_dict(orient="records"))
            else:
                df["date"] = df["date"].astype(str)
                for col in df.select_dtypes(include=["datetime64[ns]"]).columns:
                    df[col] = df[col].apply(
                        lambda x: x.isoformat() if pd.notna(x) else None
                    )
                result[key] = sanitize_for_json(df.to_dict(orient="records"))

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
        raise ValidationError("Request body is required")

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


@api.route("/settings/credentials", methods=["GET"])
@login_required
def api_get_credentials():
    creds = get_user_credentials(current_user.id)
    whoop_client_id = os.getenv("WHOOP_CLIENT_ID")
    whoop_auth_url = "/whoop/authorize" if whoop_client_id else None

    whoop_has_token = False
    whoop_token_expired = False

    if creds is not None:
        whoop_has_token = bool(creds.encrypted_whoop_access_token)
        if whoop_has_token and creds.whoop_token_expires_at:
            expires_at = creds.whoop_token_expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)
            whoop_token_expired = expires_at < datetime.now(UTC)

        if whoop_token_expired and creds.encrypted_whoop_refresh_token:
            logger.info("whoop_token_expired_refreshing", user_id=current_user.id)
            if refresh_whoop_token_for_user(current_user.id):
                whoop_token_expired = False
                logger.info(
                    "whoop_token_refreshed_proactively", user_id=current_user.id
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
    with get_db_session_context() as db:
        syncs = db.scalars(
            select(DataSync)
            .filter_by(user_id=current_user.id)
            .order_by(DataSync.last_sync_timestamp.desc())
        ).all()

        return jsonify(
            [
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
            ]
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

    thread = threading.Thread(target=run_sync, daemon=True)
    thread.start()

    sync_type = "full" if full_sync else f"{days}-day" if days else "two-phase"
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
