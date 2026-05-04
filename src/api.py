import atexit
import math
import os
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from typing import Any

import pandas as pd
import pydantic
from flask import Blueprint, jsonify, request, session
from flask_login import current_user, login_required, login_user, logout_user
from pydantic import BaseModel
from sqlalchemy import func, select

from analytics import TrendMode
from analytics.pipeline import get_or_compute_snapshot
from api_schemas import (
    BiomarkerCreate,
    ClinicalAlertStatusUpdate,
    EightSleepCredentialsRequest,
    FunctionalTestCreate,
    GarminCredentialsRequest,
    GoalCreate,
    GoalUpdate,
    HealthEventCreate,  # type: ignore[attr-defined]
    HealthEventUpdate,  # type: ignore[attr-defined]
    HealthNoteCreate,  # type: ignore[attr-defined]
    HevyCredentialsRequest,
    InterventionCreate,
    InterventionUpdate,
    LoginRequest,
    ProfileUpdate,
    ProtocolCreate,  # type: ignore[attr-defined]
    ProtocolUpdate,  # type: ignore[attr-defined]
    ThresholdSettings,
    WorkoutProgramCreate,
    WorkoutProgramUpdate,
)
from data_loaders import (
    get_detailed_workout_data,
    get_garmin_activities_data,
    get_workout_volume_data,
    load_data_for_user,
)
from database import get_db_session_context
from date_utils import parse_iso_date, utcnow
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
    BotMessage,
    ClinicalAlertEvent,
    DataSync,
    ExerciseTemplate,
    FunctionalTest,
    GarminRacePrediction,
    HealthEvent,  # type: ignore[attr-defined]
    HealthNote,  # type: ignore[attr-defined]
    Intervention,
    LongevityGoal,
    ProgramDay,
    ProgramExercise,
    Protocol,  # type: ignore[attr-defined]
    User,
    UserCredentials,
    UserSettings,
    WorkoutProgram,
)
from pull_hevy_data import sync_hevy_exercise_templates_for_user
from pull_whoop_data import refresh_whoop_token_for_user
from routes import UserModel
from security import encrypt_data_for_user, verify_password
from settings import get_settings
from sync_manager import is_sync_in_progress
from utils import get_user_credentials

api = Blueprint("api", __name__, url_prefix="/api")
logger = get_logger(__name__)
WEB_CHAT_ID = 0  # Reserved chat_id for web interface
MSG_BODY_REQUIRED = "Request body is required"
_sync_executor = ThreadPoolExecutor(max_workers=4)
atexit.register(_sync_executor.shutdown, wait=False)


def _parse_body[T: BaseModel](model_class: type[T]) -> T:
    data = request.get_json()
    if not data:
        raise ValidationError(MSG_BODY_REQUIRED)
    try:
        return model_class.model_validate(data)  # type: ignore[no-any-return]
    except pydantic.ValidationError as e:
        first = e.errors()[0]
        field = ".".join(str(loc) for loc in first.get("loc", []))
        msg = first["msg"]
        if msg.startswith("Value error, "):
            msg = msg[13:]
        raise ValidationError(msg, field=field or None) from None


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
    body = _parse_body(LoginRequest)

    try:
        username = body.username
        password = body.password
        with get_db_session_context() as db:
            user = db.scalars(select(User).filter_by(username=username)).first()
            if user and verify_password(password, user.password_hash):  # type: ignore[arg-type]
                session.clear()
                user_model = UserModel(user.id, user.username)  # type: ignore[arg-type]
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
    for record in records:
        for key, value in record.items():
            if (
                isinstance(value, float) and not math.isfinite(value)
            ) or value is pd.NaT:
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
        return parse_iso_date(start_str), parse_iso_date(end_str)
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
    for col in df.select_dtypes(include=["datetime64", "datetimetz"]).columns:
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
            start_date = parse_iso_date(start_date)
            end_date = parse_iso_date(end_date)
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
            start_date = parse_iso_date(start_date)
            end_date = parse_iso_date(end_date)
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


@api.route("/settings/thresholds", methods=["PUT"])
@login_required
def api_save_thresholds():
    body = _parse_body(ThresholdSettings)
    validated = body.model_dump(exclude_unset=True, exclude_none=True)

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


def _mask_email(email: str | None) -> str | None:
    if not email or "@" not in email:
        return None
    local, domain = email.split("@", 1)
    if not local:
        return None
    visible = local[:2] if len(local) > 2 else local[0]
    return f"{visible}***@{domain}"


def _mask_api_key(encrypted_key: str | None) -> str | None:
    if not encrypted_key:
        return None
    return "***...configured"


def _invalidate_garmin_token_store(user_id: int) -> None:
    import shutil

    token_dir = f"/app/.garminconnect/user_{user_id}"
    shutil.rmtree(token_dir, ignore_errors=True)


def _build_credentials_response(user_id: int) -> dict:
    creds = get_user_credentials(user_id)
    whoop_client_id = os.getenv("WHOOP_CLIENT_ID")
    whoop_auth_url = "/whoop/authorize" if whoop_client_id else None
    whoop_has_token, whoop_token_expired = _check_whoop_token_status(creds)
    whoop_token_expired = _maybe_refresh_whoop_token(
        creds, user_id, whoop_token_expired
    )

    return {
        "garmin_configured": bool(
            creds and creds.garmin_email and creds.encrypted_garmin_password
        ),
        "garmin_email_hint": _mask_email(creds.garmin_email if creds else None),  # type: ignore[arg-type]
        "hevy_configured": bool(creds and creds.encrypted_hevy_api_key),
        "hevy_api_key_hint": _mask_api_key(
            creds.encrypted_hevy_api_key if creds else None  # type: ignore[arg-type]
        ),
        "whoop_configured": whoop_has_token and not whoop_token_expired,
        "whoop_token_expired": whoop_token_expired,
        "whoop_auth_url": whoop_auth_url,
        "eight_sleep_configured": bool(
            creds and creds.eight_sleep_email and creds.encrypted_eight_sleep_password
        ),
        "eight_sleep_email_hint": _mask_email(
            creds.eight_sleep_email if creds else None  # type: ignore[arg-type]
        ),
    }


@api.route("/settings/credentials", methods=["GET"])
@login_required
def api_get_credentials():
    return jsonify(_build_credentials_response(current_user.id))


@api.route("/settings/credentials/garmin", methods=["PUT"])
@login_required
@limiter.limit("10 per hour")
def api_update_garmin_credentials():
    body = _parse_body(GarminCredentialsRequest)
    encrypted_password = encrypt_data_for_user(body.password, current_user.id)

    with get_db_session_context() as db:
        creds = db.scalars(
            select(UserCredentials).filter_by(user_id=current_user.id)
        ).first()
        if not creds:
            creds = UserCredentials(user_id=current_user.id)
            db.add(creds)

        creds.garmin_email = body.email  # type: ignore[assignment]
        creds.encrypted_garmin_password = encrypted_password  # type: ignore[assignment]

    _invalidate_garmin_token_store(current_user.id)
    logger.info("garmin_credentials_updated", user_id=current_user.id)
    return jsonify(_build_credentials_response(current_user.id))


@api.route("/settings/credentials/hevy", methods=["PUT"])
@login_required
@limiter.limit("10 per hour")
def api_update_hevy_credentials():
    body = _parse_body(HevyCredentialsRequest)
    encrypted_key = encrypt_data_for_user(body.api_key, current_user.id)

    with get_db_session_context() as db:
        creds = db.scalars(
            select(UserCredentials).filter_by(user_id=current_user.id)
        ).first()
        if not creds:
            creds = UserCredentials(user_id=current_user.id)
            db.add(creds)

        creds.encrypted_hevy_api_key = encrypted_key  # type: ignore[assignment]

    logger.info("hevy_credentials_updated", user_id=current_user.id)
    return jsonify(_build_credentials_response(current_user.id))


@api.route("/settings/credentials/garmin", methods=["DELETE"])
@login_required
@limiter.limit("10 per hour")
def api_delete_garmin_credentials():
    with get_db_session_context() as db:
        creds = db.scalars(
            select(UserCredentials).filter_by(user_id=current_user.id)
        ).first()
        if creds:
            creds.garmin_email = None  # type: ignore[assignment]
            creds.encrypted_garmin_password = None  # type: ignore[assignment]

    _invalidate_garmin_token_store(current_user.id)
    logger.info("garmin_credentials_deleted", user_id=current_user.id)
    return jsonify(_build_credentials_response(current_user.id))


@api.route("/settings/credentials/hevy", methods=["DELETE"])
@login_required
@limiter.limit("10 per hour")
def api_delete_hevy_credentials():
    with get_db_session_context() as db:
        creds = db.scalars(
            select(UserCredentials).filter_by(user_id=current_user.id)
        ).first()
        if creds:
            creds.encrypted_hevy_api_key = None  # type: ignore[assignment]

    logger.info("hevy_credentials_deleted", user_id=current_user.id)
    return jsonify(_build_credentials_response(current_user.id))


@api.route("/settings/credentials/garmin/test", methods=["POST"])
@login_required
@limiter.limit("3 per hour")
def api_test_garmin_credentials():
    body = _parse_body(GarminCredentialsRequest)

    try:
        from garminconnect import (
            Garmin,
            GarminConnectAuthenticationError,
            GarminConnectConnectionError,
            GarminConnectTooManyRequestsError,
        )

        garmin_api = Garmin(body.email, body.password)
        garmin_api.login()

        token_dir = f"/app/.garminconnect/user_{current_user.id}"
        os.makedirs(token_dir, exist_ok=True)
        garmin_api.client.dump(token_dir)
        logger.info("garmin_credentials_test_success", user_id=current_user.id)
        return jsonify({"success": True})
    except GarminConnectAuthenticationError:
        logger.warning("garmin_credentials_test_failed", user_id=current_user.id)
        return jsonify({"success": False, "error": "Invalid credentials"})
    except GarminConnectTooManyRequestsError:
        logger.warning("garmin_credentials_test_rate_limited", user_id=current_user.id)
        return jsonify(
            {"success": False, "error": "Too many requests — try again later"}
        )
    except GarminConnectConnectionError:
        logger.warning(
            "garmin_credentials_test_connection_error", user_id=current_user.id
        )
        return jsonify({"success": False, "error": "Cannot reach Garmin servers"})
    except Exception:
        logger.exception("garmin_credentials_test_error", user_id=current_user.id)
        return jsonify({"success": False, "error": "Connection error"})


@api.route("/settings/credentials/hevy/test", methods=["POST"])
@login_required
@limiter.limit("3 per hour")
def api_test_hevy_credentials():
    body = _parse_body(HevyCredentialsRequest)

    try:
        import requests as http_requests

        resp = http_requests.get(
            "https://api.hevyapp.com/v1/workouts",
            headers={"api-key": body.api_key},
            params={"page": 1, "pageSize": 1},
            timeout=10,
        )
        if resp.status_code == 200:
            logger.info("hevy_credentials_test_success", user_id=current_user.id)
            return jsonify({"success": True})
        if resp.status_code in (401, 403):
            logger.warning("hevy_credentials_test_failed", user_id=current_user.id)
            return jsonify({"success": False, "error": "Invalid API key"})
        logger.warning(
            "hevy_credentials_test_unexpected_status",
            user_id=current_user.id,
            status=resp.status_code,
        )
        return jsonify({"success": False, "error": "Unexpected response from Hevy"})
    except Exception:
        logger.exception("hevy_credentials_test_error", user_id=current_user.id)
        return jsonify({"success": False, "error": "Connection error"})


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
                            s.last_sync_date.isoformat() if s.last_sync_date else None  # type: ignore[union-attr]
                        ),
                        "last_sync_timestamp": (
                            s.last_sync_timestamp.isoformat() + "Z"
                            if s.last_sync_timestamp  # type: ignore[truthy-function]
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


@api.route("/sync/backoff-status", methods=["GET"])
@login_required
def api_sync_backoff_status():
    from sync_backoff import SyncBackoffManager

    manager = SyncBackoffManager()
    sources = ["garmin", "hevy", "whoop", "eight_sleep"]
    result = {}
    for source in sources:
        result[source] = manager.get_status(current_user.id, source)
    return jsonify(result)


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
                existing_sync.last_sync_timestamp = now  # type: ignore[assignment]
                existing_sync.last_sync_date = now.date()  # type: ignore[assignment]
                existing_sync.records_synced = records_synced  # type: ignore[assignment]
                existing_sync.status = status  # type: ignore[assignment]
                existing_sync.error_message = error_message  # type: ignore[assignment]
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


def _is_source_disabled(source: DataSource) -> bool:
    disabled = os.getenv("SYNC_DISABLED_SOURCES", "")
    if not disabled:
        return False
    skip = {s.strip().lower() for s in disabled.split(",")}
    return source.value.lower() in skip


def _handle_sync_request(
    source: DataSource,
    source_name: str,
    sync_func_getter: Callable[[], Callable[..., dict[str, Any] | None]],
):
    if _is_source_disabled(source):
        return jsonify({"error": f"{source_name} sync is disabled"}), 503

    user_id = current_user.id

    if is_sync_in_progress(user_id, source):
        raise ConflictError(
            f"{source_name} sync already in progress",
            source=source_name.lower(),
        )

    # Manual sync clears any backoff state so the user can retry after exhaustion
    from sync_backoff import SyncBackoffManager

    SyncBackoffManager().record_success(user_id, source.value)

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
                    user_id, source.value, result, result.get("success", False)
                )
            elif days:
                result = normalize_sync_result(sync_func(user_id, days=days))
                _update_data_sync(
                    user_id, source.value, result, result.get("success", False)
                )
            else:
                _run_two_phase_sync(user_id, sync_func, source.value)
        except Exception as e:
            _update_data_sync(
                user_id,
                source.value,
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


@api.route("/settings/credentials/eight_sleep", methods=["PUT"])
@login_required
@limiter.limit("10 per hour")
def api_update_eight_sleep_credentials():
    body = _parse_body(EightSleepCredentialsRequest)
    encrypted_password = encrypt_data_for_user(body.password, current_user.id)

    with get_db_session_context() as db:
        creds = db.scalars(
            select(UserCredentials).filter_by(user_id=current_user.id)
        ).first()
        if not creds:
            creds = UserCredentials(user_id=current_user.id)
            db.add(creds)

        creds.eight_sleep_email = body.email  # type: ignore[assignment]
        creds.encrypted_eight_sleep_password = encrypted_password  # type: ignore[assignment]
        creds.encrypted_eight_sleep_access_token = None  # type: ignore[assignment]
        creds.eight_sleep_token_expires_at = None  # type: ignore[assignment]

    logger.info("eight_sleep_credentials_updated", user_id=current_user.id)
    return jsonify(_build_credentials_response(current_user.id))


@api.route("/settings/credentials/eight_sleep", methods=["DELETE"])
@login_required
@limiter.limit("10 per hour")
def api_delete_eight_sleep_credentials():
    with get_db_session_context() as db:
        creds = db.scalars(
            select(UserCredentials).filter_by(user_id=current_user.id)
        ).first()
        if creds:
            creds.eight_sleep_email = None  # type: ignore[assignment]
            creds.encrypted_eight_sleep_password = None  # type: ignore[assignment]
            creds.encrypted_eight_sleep_access_token = None  # type: ignore[assignment]
            creds.eight_sleep_token_expires_at = None  # type: ignore[assignment]

    logger.info("eight_sleep_credentials_deleted", user_id=current_user.id)
    return jsonify(_build_credentials_response(current_user.id))


@api.route("/settings/credentials/eight_sleep/test", methods=["POST"])
@login_required
@limiter.limit("3 per hour")
def api_test_eight_sleep_credentials():
    body = _parse_body(EightSleepCredentialsRequest)

    try:
        from pull_eight_sleep_data import EightSleepAPIClient

        client = EightSleepAPIClient(body.email, body.password)
        try:
            client.authenticate()
            logger.info("eight_sleep_credentials_test_success", user_id=current_user.id)
            return jsonify({"success": True})
        finally:
            client.close()
    except Exception:
        logger.exception("eight_sleep_credentials_test_error", user_id=current_user.id)
        return jsonify(
            {"success": False, "error": "Invalid credentials or connection error"}
        )


@api.route("/sync/eight_sleep", methods=["POST"])
@login_required
@limiter.limit("3000 per hour")
def api_sync_eight_sleep():
    def get_sync_func():
        from pull_eight_sleep_data import sync_eight_sleep_data_for_user

        return sync_eight_sleep_data_for_user

    return _handle_sync_request(DataSource.EIGHT_SLEEP, "Eight Sleep", get_sync_func)


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
                    if settings and settings.birth_date  # type: ignore[truthy-function]
                    else None
                ),
                "gender": settings.gender if settings else None,
                "height_cm": settings.height_cm if settings else None,
            }
        )


@api.route("/settings/profile", methods=["PUT"])
@login_required
def api_update_profile():
    body = _parse_body(ProfileUpdate)

    with get_db_session_context() as db:
        settings = db.scalars(
            select(UserSettings).filter_by(user_id=current_user.id)
        ).first()
        if not settings:
            settings = UserSettings(user_id=current_user.id)
            db.add(settings)

        if "birth_date" in body.model_fields_set:
            settings.birth_date = body.birth_date  # type: ignore[assignment]
        if "gender" in body.model_fields_set:
            settings.gender = body.gender  # type: ignore[assignment]
        if "height_cm" in body.model_fields_set:
            settings.height_cm = body.height_cm  # type: ignore[assignment]

        db.commit()
        return jsonify(
            {
                "birth_date": (
                    settings.birth_date.isoformat() if settings.birth_date else None  # type: ignore[union-attr,truthy-function]
                ),
                "gender": settings.gender,
                "height_cm": settings.height_cm,
            }
        )


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
    body = _parse_body(BiomarkerCreate)

    with get_db_session_context() as db:
        biomarker = BloodBiomarker(
            user_id=current_user.id,
            **body.model_dump(),
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
    body = _parse_body(InterventionCreate)

    with get_db_session_context() as db:
        intervention = Intervention(
            user_id=current_user.id,
            active=True,
            **body.model_dump(),
        )
        db.add(intervention)
        db.commit()
        return jsonify(_serialize_model(intervention, INTERVENTION_FIELDS)), 201


@api.route("/longevity/interventions/<int:intervention_id>", methods=["PUT"])
@login_required
def api_update_intervention(intervention_id: int):
    body = _parse_body(InterventionUpdate)

    with get_db_session_context() as db:
        row = db.scalars(
            select(Intervention).filter_by(id=intervention_id, user_id=current_user.id)
        ).first()
        if not row:
            raise NotFoundError("Intervention")

        for field in body.model_fields_set:
            setattr(row, field, getattr(body, field))

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


# ================================ Health Events ================================

HEALTH_EVENT_FIELDS = [
    "id",
    "name",
    "domain",
    "start_ts",
    "end_ts",
    "dosage",
    "notes",
    "attributes",
    "tags",
    "protocol_id",
]


def _serialize_health_event(event: HealthEvent) -> dict:
    return {
        "id": event.id,
        "name": event.name,
        "domain": event.domain,
        "start_ts": event.start_ts.isoformat() if event.start_ts else None,
        "end_ts": event.end_ts.isoformat() if event.end_ts else None,
        "dosage": event.dosage,
        "notes": event.notes,
        "attributes": event.attributes or {},
        "tags": event.tags or [],
        "protocol_id": event.protocol_id,
        "type": "point" if event.end_ts is None else "duration",
    }


@api.route("/longevity/events", methods=["GET"])
@login_required
def api_get_health_events():
    days = request.args.get("days", type=int)
    with get_db_session_context() as db:
        query = select(HealthEvent).filter_by(user_id=current_user.id)
        if days:
            cutoff = datetime.now(UTC) - timedelta(days=days)
            query = query.filter(HealthEvent.start_ts >= cutoff)
        query = query.order_by(HealthEvent.start_ts.desc())
        rows = db.scalars(query).all()
        return jsonify([_serialize_health_event(r) for r in rows])


@api.route("/longevity/events", methods=["POST"])
@login_required
def api_create_health_event():
    body = _parse_body(HealthEventCreate)

    start_ts = body.start_ts
    if start_ts is None:
        start_ts = datetime.now(UTC)
    elif not hasattr(start_ts, "hour"):
        start_ts = datetime(start_ts.year, start_ts.month, start_ts.day, tzinfo=UTC)
    elif start_ts.tzinfo is None:
        start_ts = start_ts.replace(tzinfo=UTC)

    end_ts = body.end_ts
    if end_ts is not None and not hasattr(end_ts, "hour"):
        end_ts = datetime(end_ts.year, end_ts.month, end_ts.day, 23, 59, 59, tzinfo=UTC)
    elif end_ts is not None and end_ts.tzinfo is None:
        end_ts = end_ts.replace(tzinfo=UTC)

    with get_db_session_context() as db:
        event = HealthEvent(
            user_id=current_user.id,
            name=body.name,
            domain=body.domain,
            start_ts=start_ts,
            end_ts=end_ts,
            dosage=body.dosage,
            notes=body.notes,
            attributes=body.attributes,
            tags=body.tags,
            protocol_id=body.protocol_id,
        )
        db.add(event)
        db.commit()
        return jsonify(_serialize_health_event(event)), 201


@api.route("/longevity/events/<int:event_id>", methods=["PUT"])
@login_required
def api_update_health_event(event_id: int):
    body = _parse_body(HealthEventUpdate)
    with get_db_session_context() as db:
        row = db.scalars(
            select(HealthEvent).filter_by(id=event_id, user_id=current_user.id)
        ).first()
        if not row:
            raise NotFoundError("HealthEvent")
        for field in body.model_fields_set:
            setattr(row, field, getattr(body, field))
        db.commit()
        return jsonify(_serialize_health_event(row))


@api.route("/longevity/events/<int:event_id>", methods=["DELETE"])
@login_required
def api_delete_health_event(event_id: int):
    with get_db_session_context() as db:
        row = db.scalars(
            select(HealthEvent).filter_by(id=event_id, user_id=current_user.id)
        ).first()
        if not row:
            raise NotFoundError("HealthEvent")
        db.delete(row)
        db.commit()
        return jsonify({"deleted": True})


# ================================ Protocols ====================================


def _serialize_protocol(p: Protocol) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "domain": p.domain,
        "start_date": p.start_date.isoformat() if p.start_date else None,
        "end_date": p.end_date.isoformat() if p.end_date else None,
        "dosage": p.dosage,
        "frequency": p.frequency,
        "notes": p.notes,
        "tags": p.tags or [],
        "active": p.end_date is None,
    }


@api.route("/longevity/protocols", methods=["GET"])
@login_required
def api_get_protocols():
    active_only = request.args.get("active", "").lower() == "true"
    with get_db_session_context() as db:
        query = select(Protocol).filter_by(user_id=current_user.id)
        if active_only:
            query = query.filter(Protocol.end_date.is_(None))
        query = query.order_by(Protocol.start_date.desc())
        rows = db.scalars(query).all()
        return jsonify([_serialize_protocol(r) for r in rows])


@api.route("/longevity/protocols", methods=["POST"])
@login_required
def api_create_protocol():
    body = _parse_body(ProtocolCreate)
    with get_db_session_context() as db:
        protocol = Protocol(
            user_id=current_user.id,
            name=body.name,
            domain=body.domain,
            start_date=body.start_date,
            end_date=body.end_date,
            dosage=body.dosage,
            frequency=body.frequency,
            notes=body.notes,
            tags=body.tags,
        )
        db.add(protocol)
        db.commit()
        return jsonify(_serialize_protocol(protocol)), 201


@api.route("/longevity/protocols/<int:protocol_id>", methods=["PUT"])
@login_required
def api_update_protocol(protocol_id: int):
    body = _parse_body(ProtocolUpdate)
    with get_db_session_context() as db:
        row = db.scalars(
            select(Protocol).filter_by(id=protocol_id, user_id=current_user.id)
        ).first()
        if not row:
            raise NotFoundError("Protocol")
        for field in body.model_fields_set:
            setattr(row, field, getattr(body, field))
        db.commit()
        return jsonify(_serialize_protocol(row))


@api.route("/longevity/protocols/<int:protocol_id>", methods=["DELETE"])
@login_required
def api_delete_protocol(protocol_id: int):
    with get_db_session_context() as db:
        row = db.scalars(
            select(Protocol).filter_by(id=protocol_id, user_id=current_user.id)
        ).first()
        if not row:
            raise NotFoundError("Protocol")
        db.delete(row)
        db.commit()
        return jsonify({"deleted": True})


# ================================ Health Notes =================================


def _serialize_health_note(n: HealthNote) -> dict:
    return {
        "id": n.id,
        "text": n.text,
        "attributes": n.attributes or {},
        "tags": n.tags or [],
        "created_at": n.created_at.isoformat() if n.created_at else None,
    }


@api.route("/longevity/notes", methods=["GET"])
@login_required
def api_get_health_notes():
    days = request.args.get("days", type=int, default=30)
    with get_db_session_context() as db:
        cutoff = datetime.now(UTC) - timedelta(days=days)
        rows = db.scalars(
            select(HealthNote)
            .filter(
                HealthNote.user_id == current_user.id, HealthNote.created_at >= cutoff
            )
            .order_by(HealthNote.created_at.desc())
        ).all()
        return jsonify([_serialize_health_note(r) for r in rows])


@api.route("/longevity/notes", methods=["POST"])
@login_required
def api_create_health_note():
    body = _parse_body(HealthNoteCreate)
    with get_db_session_context() as db:
        note = HealthNote(
            user_id=current_user.id,
            text=body.text,
            attributes=body.attributes,
            tags=body.tags,
        )
        db.add(note)
        db.commit()
        return jsonify(_serialize_health_note(note)), 201


@api.route("/longevity/notes/<int:note_id>", methods=["DELETE"])
@login_required
def api_delete_health_note(note_id: int):
    with get_db_session_context() as db:
        row = db.scalars(
            select(HealthNote).filter_by(id=note_id, user_id=current_user.id)
        ).first()
        if not row:
            raise NotFoundError("HealthNote")
        db.delete(row)
        db.commit()
        return jsonify({"deleted": True})


# ================================ Unified Log ==================================


@api.route("/longevity/log", methods=["GET"])
@login_required
def api_get_unified_log():
    days = request.args.get("days", type=int, default=14)
    cutoff_date = datetime.now(UTC) - timedelta(days=days)

    with get_db_session_context() as db:
        events = db.scalars(
            select(HealthEvent)
            .filter(
                HealthEvent.user_id == current_user.id,
                HealthEvent.start_ts >= cutoff_date,
            )
            .order_by(HealthEvent.start_ts.desc())
        ).all()

        protocols = db.scalars(
            select(Protocol)
            .filter(Protocol.user_id == current_user.id)
            .filter(
                (Protocol.end_date.is_(None))
                | (Protocol.start_date >= cutoff_date.date())
            )
            .order_by(Protocol.start_date.desc())
        ).all()

        notes = db.scalars(
            select(HealthNote)
            .filter(
                HealthNote.user_id == current_user.id,
                HealthNote.created_at >= cutoff_date,
            )
            .order_by(HealthNote.created_at.desc())
        ).all()

    return jsonify(
        {
            "events": [_serialize_health_event(e) for e in events],
            "protocols": [_serialize_protocol(p) for p in protocols],
            "notes": [_serialize_health_note(n) for n in notes],
            "days": days,
        }
    )


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
    body = _parse_body(FunctionalTestCreate)

    with get_db_session_context() as db:
        test = FunctionalTest(
            user_id=current_user.id,
            **body.model_dump(),
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
    body = _parse_body(GoalCreate)

    with get_db_session_context() as db:
        goal = LongevityGoal(
            user_id=current_user.id,
            **body.model_dump(),
        )
        db.add(goal)
        db.commit()
        return jsonify(_serialize_model(goal, GOAL_FIELDS)), 201


@api.route("/longevity/goals/<int:goal_id>", methods=["PUT"])
@login_required
def api_update_goal(goal_id: int):
    body = _parse_body(GoalUpdate)

    with get_db_session_context() as db:
        row = db.scalars(
            select(LongevityGoal).filter_by(id=goal_id, user_id=current_user.id)
        ).first()
        if not row:
            raise NotFoundError("Goal")

        for field in body.model_fields_set:
            setattr(row, field, getattr(body, field))

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


RACE_PREDICTION_FIELDS = [
    "date",
    "prediction_5k_seconds",
    "prediction_10k_seconds",
    "prediction_half_marathon_seconds",
    "prediction_marathon_seconds",
    "vo2_max_value",
]


@api.route("/data/race-predictions", methods=["GET"])
@login_required
def api_get_race_predictions():
    start_date, end_date = _parse_date_range(
        request.args.get("start_date"), request.args.get("end_date")
    )
    with get_db_session_context() as db:
        rows = db.scalars(
            select(GarminRacePrediction)
            .filter(
                GarminRacePrediction.user_id == current_user.id,
                GarminRacePrediction.date >= start_date,
                GarminRacePrediction.date <= end_date,
            )
            .order_by(GarminRacePrediction.date.desc())
        ).all()
        return jsonify([_serialize_model(r, RACE_PREDICTION_FIELDS) for r in rows])


CLINICAL_ALERT_FIELDS = [
    "id",
    "alert_type",
    "severity",
    "status",
    "details_json",
    "first_detected_at",
    "last_detected_at",
    "acknowledged_at",
    "resolved_at",
]


@api.route("/clinical-alerts", methods=["GET"])
@login_required
def api_get_clinical_alerts():
    status_filter = request.args.get("status")
    with get_db_session_context() as db:
        query = select(ClinicalAlertEvent).filter_by(user_id=current_user.id)
        if status_filter:
            query = query.filter_by(status=status_filter)
        query = query.order_by(ClinicalAlertEvent.last_detected_at.desc())
        rows = db.scalars(query).all()
        return jsonify([_serialize_model(r, CLINICAL_ALERT_FIELDS) for r in rows])


@api.route("/clinical-alerts/<int:alert_id>/status", methods=["PUT"])
@login_required
def api_update_clinical_alert_status(alert_id: int):
    body = _parse_body(ClinicalAlertStatusUpdate)
    with get_db_session_context() as db:
        row = db.scalars(
            select(ClinicalAlertEvent).filter_by(id=alert_id, user_id=current_user.id)
        ).first()
        if not row:
            raise NotFoundError("Clinical alert")
        row.status = body.status  # type: ignore[assignment]
        now = utcnow()
        if body.status == "acknowledged" and row.acknowledged_at is None:
            row.acknowledged_at = now  # type: ignore[assignment]
        elif body.status == "resolved" and row.resolved_at is None:
            row.resolved_at = now  # type: ignore[assignment]
        db.commit()
        return jsonify(_serialize_model(row, CLINICAL_ALERT_FIELDS))


# ----------------------------- Workout Programs -----------------------------

_WORKOUT_PROGRAM = "Workout program"


def _serialize_program_exercise(ex: ProgramExercise) -> dict:
    return {
        "id": ex.id,
        "exercise_order": ex.exercise_order,
        "exercise_title": ex.exercise_title,
        "template_id": ex.template_id,
        "target_sets": ex.target_sets,
        "target_reps_min": ex.target_reps_min,
        "target_reps_max": ex.target_reps_max,
        "target_rpe_min": ex.target_rpe_min,
        "target_rpe_max": ex.target_rpe_max,
        "target_weight_kg": ex.target_weight_kg,
        "rest_seconds": ex.rest_seconds,
        "tempo": ex.tempo,
        "notes": ex.notes,
    }


def _serialize_program_day(day: ProgramDay) -> dict:
    return {
        "id": day.id,
        "day_order": day.day_order,
        "name": day.name,
        "focus": day.focus,
        "notes": day.notes,
        "exercises": [_serialize_program_exercise(e) for e in day.exercises],
    }


def _serialize_program(program: WorkoutProgram, *, include_days: bool = True) -> dict:
    total_exercises = sum(len(d.exercises) for d in program.days)
    base = {
        "id": program.id,
        "name": program.name,
        "description": program.description,
        "goal": program.goal,
        "start_date": program.start_date.isoformat() if program.start_date else None,  # type: ignore[union-attr,truthy-function]
        "end_date": program.end_date.isoformat() if program.end_date else None,  # type: ignore[union-attr,truthy-function]
        "is_active": program.is_active,
        "archived_at": (
            program.archived_at.isoformat() if program.archived_at else None  # type: ignore[union-attr,truthy-function]
        ),
        "created_at": (program.created_at.isoformat() if program.created_at else None),  # type: ignore[union-attr,truthy-function]
        "updated_at": (program.updated_at.isoformat() if program.updated_at else None),  # type: ignore[union-attr,truthy-function]
        "day_count": len(program.days),
        "exercise_count": total_exercises,
    }
    if include_days:
        base["days"] = [_serialize_program_day(d) for d in program.days]
    return base


def _validate_template_ids(db, user_id: int, template_ids: set[int]) -> set[int]:
    """Confirm every template_id referenced belongs to the user. Returns the
    set of valid IDs; unknown IDs are silently dropped (FK is nullable, so we
    just null them out to keep the program saveable)."""
    if not template_ids:
        return set()
    rows = db.scalars(
        select(ExerciseTemplate.id).filter(
            ExerciseTemplate.user_id == user_id,
            ExerciseTemplate.id.in_(template_ids),
        )
    ).all()
    return set(rows)


def _materialize_days(
    db,
    program: WorkoutProgram,
    days_input: list,
    valid_template_ids: set[int],
) -> None:
    """Create ProgramDay + ProgramExercise rows from validated inputs.
    The caller is responsible for clearing existing days first when updating.
    """
    for day_in in days_input:
        day = ProgramDay(
            program_id=program.id,
            day_order=day_in.day_order,
            name=day_in.name,
            focus=day_in.focus,
            notes=day_in.notes,
        )
        db.add(day)
        db.flush()  # need day.id before adding exercises
        for ex_in in day_in.exercises:
            template_id = ex_in.template_id
            if template_id is not None and template_id not in valid_template_ids:
                template_id = None
            db.add(
                ProgramExercise(
                    day_id=day.id,
                    template_id=template_id,
                    exercise_order=ex_in.exercise_order,
                    exercise_title=ex_in.exercise_title,
                    target_sets=ex_in.target_sets,
                    target_reps_min=ex_in.target_reps_min,
                    target_reps_max=ex_in.target_reps_max,
                    target_rpe_min=ex_in.target_rpe_min,
                    target_rpe_max=ex_in.target_rpe_max,
                    target_weight_kg=ex_in.target_weight_kg,
                    rest_seconds=ex_in.rest_seconds,
                    tempo=ex_in.tempo,
                    notes=ex_in.notes,
                )
            )


def _deactivate_other_programs(db, user_id: int, except_id: int | None) -> None:
    query = select(WorkoutProgram).filter(
        WorkoutProgram.user_id == user_id,
        WorkoutProgram.is_active.is_(True),
    )
    if except_id is not None:
        query = query.filter(WorkoutProgram.id != except_id)
    others = db.scalars(query).all()
    now = utcnow()
    for other in others:
        other.is_active = False  # type: ignore[assignment]
        if other.archived_at is None:
            other.archived_at = now  # type: ignore[assignment]
        if other.end_date is None:
            other.end_date = now.date()  # type: ignore[assignment]


@api.route("/programs", methods=["GET"])
@login_required
def api_list_programs():
    """List all programs for the current user, newest first."""
    with get_db_session_context() as db:
        rows = db.scalars(
            select(WorkoutProgram)
            .filter_by(user_id=current_user.id)
            .order_by(
                WorkoutProgram.is_active.desc(),
                WorkoutProgram.start_date.desc(),
                WorkoutProgram.id.desc(),
            )
        ).all()
        # Lightweight summary for the list view; days fetched per-detail.
        return jsonify([_serialize_program(p, include_days=False) for p in rows])


@api.route("/programs/active", methods=["GET"])
@login_required
def api_get_active_program():
    with get_db_session_context() as db:
        row = db.scalars(
            select(WorkoutProgram).filter_by(user_id=current_user.id, is_active=True)
        ).first()
        if not row:
            return jsonify(None)
        return jsonify(_serialize_program(row, include_days=True))


@api.route("/programs/<int:program_id>", methods=["GET"])
@login_required
def api_get_program(program_id: int):
    with get_db_session_context() as db:
        row = db.scalars(
            select(WorkoutProgram).filter_by(id=program_id, user_id=current_user.id)
        ).first()
        if not row:
            raise NotFoundError(_WORKOUT_PROGRAM)
        return jsonify(_serialize_program(row, include_days=True))


@api.route("/programs", methods=["POST"])
@login_required
def api_create_program():
    body = _parse_body(WorkoutProgramCreate)

    with get_db_session_context() as db:
        program = WorkoutProgram(
            user_id=current_user.id,
            name=body.name,
            description=body.description,
            goal=body.goal,
            start_date=body.start_date,
            is_active=False,  # set after deactivating others
        )
        db.add(program)
        db.flush()

        template_ids = {
            ex.template_id
            for d in body.days
            for ex in d.exercises
            if ex.template_id is not None
        }
        valid_template_ids = _validate_template_ids(db, current_user.id, template_ids)
        _materialize_days(db, program, body.days, valid_template_ids)

        if body.activate:
            _deactivate_other_programs(db, current_user.id, except_id=program.id)  # type: ignore[arg-type]
            db.flush()
            program.is_active = True  # type: ignore[assignment]

        db.commit()
        db.refresh(program)
        return jsonify(_serialize_program(program, include_days=True)), 201


@api.route("/programs/<int:program_id>", methods=["PUT"])
@login_required
def api_update_program(program_id: int):
    body = _parse_body(WorkoutProgramUpdate)

    with get_db_session_context() as db:
        program = db.scalars(
            select(WorkoutProgram).filter_by(id=program_id, user_id=current_user.id)
        ).first()
        if not program:
            raise NotFoundError(_WORKOUT_PROGRAM)

        for field in ("name", "description", "goal", "start_date", "end_date"):
            if field in body.model_fields_set:
                setattr(program, field, getattr(body, field))

        if body.days is not None:
            # Replace day/exercise structure wholesale.
            for d in list(program.days):
                db.delete(d)
            db.flush()
            template_ids = {
                ex.template_id
                for d in body.days
                for ex in d.exercises
                if ex.template_id is not None
            }
            valid_template_ids = _validate_template_ids(
                db, current_user.id, template_ids
            )
            _materialize_days(db, program, body.days, valid_template_ids)

        db.commit()
        db.refresh(program)
        return jsonify(_serialize_program(program, include_days=True))


@api.route("/programs/<int:program_id>/activate", methods=["POST"])
@login_required
def api_activate_program(program_id: int):
    """Make a program active. Auto-archives any other active program."""
    with get_db_session_context() as db:
        program = db.scalars(
            select(WorkoutProgram).filter_by(id=program_id, user_id=current_user.id)
        ).first()
        if not program:
            raise NotFoundError(_WORKOUT_PROGRAM)

        _deactivate_other_programs(db, current_user.id, except_id=program.id)  # type: ignore[arg-type]
        db.flush()
        program.is_active = True  # type: ignore[assignment]
        program.archived_at = None  # type: ignore[assignment]
        # Reopen end_date if it was previously closed
        program.end_date = None  # type: ignore[assignment]
        db.commit()
        db.refresh(program)
        return jsonify(_serialize_program(program, include_days=True))


@api.route("/programs/<int:program_id>/archive", methods=["POST"])
@login_required
def api_archive_program(program_id: int):
    """Mark a program as ended. Sets end_date to today if not already set."""
    with get_db_session_context() as db:
        program = db.scalars(
            select(WorkoutProgram).filter_by(id=program_id, user_id=current_user.id)
        ).first()
        if not program:
            raise NotFoundError(_WORKOUT_PROGRAM)
        program.is_active = False  # type: ignore[assignment]
        now = utcnow()
        if program.archived_at is None:
            program.archived_at = now  # type: ignore[assignment]
        if program.end_date is None:
            program.end_date = now.date()  # type: ignore[assignment]
        db.commit()
        db.refresh(program)
        return jsonify(_serialize_program(program, include_days=True))


@api.route("/programs/<int:program_id>", methods=["DELETE"])
@login_required
def api_delete_program(program_id: int):
    with get_db_session_context() as db:
        program = db.scalars(
            select(WorkoutProgram).filter_by(id=program_id, user_id=current_user.id)
        ).first()
        if not program:
            raise NotFoundError(_WORKOUT_PROGRAM)
        db.delete(program)
        db.commit()
        return jsonify({"deleted": True})


# ----------------------------- Exercise Catalog -----------------------------


EXERCISE_TEMPLATE_FIELDS = [
    "id",
    "hevy_template_id",
    "title",
    "exercise_type",
    "primary_muscle_group",
    "secondary_muscle_groups",
    "equipment",
    "is_custom",
]


@api.route("/exercise-templates", methods=["GET"])
@login_required
def api_list_exercise_templates():
    """Search-friendly list of cached Hevy exercise templates."""
    q = (request.args.get("q") or "").strip()
    muscle = (request.args.get("muscle") or "").strip()
    equipment = (request.args.get("equipment") or "").strip()
    try:
        limit = max(1, min(int(request.args.get("limit", "200")), 500))
    except ValueError:
        limit = 200

    with get_db_session_context() as db:
        query = select(ExerciseTemplate).filter_by(user_id=current_user.id)
        if q:
            query = query.filter(ExerciseTemplate.title.ilike(f"%{q}%"))
        if muscle:
            query = query.filter(
                ExerciseTemplate.primary_muscle_group.ilike(f"%{muscle}%")
            )
        if equipment:
            query = query.filter(ExerciseTemplate.equipment.ilike(f"%{equipment}%"))
        query = query.order_by(ExerciseTemplate.title.asc()).limit(limit)
        rows = db.scalars(query).all()
        return jsonify([_serialize_model(r, EXERCISE_TEMPLATE_FIELDS) for r in rows])


@api.route("/exercise-templates/sync", methods=["POST"])
@login_required
def api_sync_exercise_templates():
    """Pull the latest Hevy exercise template catalog for this user."""
    result = sync_hevy_exercise_templates_for_user(current_user.id)
    if result.get("error"):
        return jsonify(result), 400
    return jsonify(result)


# ----------------------------- Web Chat -----------------------------


@api.route("/chat/messages", methods=["GET"])
@login_required
def api_get_chat_messages():
    try:
        limit = max(1, min(int(request.args.get("limit", "50")), 100))
    except ValueError:
        limit = 50

    with get_db_session_context() as db:
        rows = (
            db.query(
                BotMessage.id,
                BotMessage.role,
                BotMessage.text_preview,
                BotMessage.model,
                BotMessage.created_at,
            )
            .filter(
                BotMessage.user_id == current_user.id,
                BotMessage.chat_id == WEB_CHAT_ID,
                BotMessage.cleared_at.is_(None),
                BotMessage.role.in_(["user", "assistant"]),
                BotMessage.text_preview.isnot(None),
                BotMessage.text_preview != "",
                ~BotMessage.text_preview.like("[Health context update]%"),
                BotMessage.text_preview != "Обновил данные. Что хочешь узнать?",
            )
            .order_by(BotMessage.created_at.asc())
            .limit(limit)
            .all()
        )

    messages = [
        {
            "id": row.id,
            "role": row.role,
            "text_preview": row.text_preview,
            "model": row.model,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]
    return jsonify({"messages": messages, "total": len(messages)})


@api.route("/chat/messages", methods=["POST"])
@login_required
@limiter.limit("30 per minute")
def api_send_chat_message():
    from agent.agent import HealthAgent
    from agent.bot_message_repo import load_recent_messages
    from agent.conversation import Conversation

    data = request.get_json()
    if not data:
        raise ValidationError(MSG_BODY_REQUIRED)
    message = (data.get("message") or "").strip()
    if not message:
        raise ValidationError("Message is required", field="message")

    conversation = Conversation(user_id=current_user.id, chat_id=WEB_CHAT_ID)
    history = load_recent_messages(current_user.id, WEB_CHAT_ID, limit=40)
    conversation.messages = history
    if history:
        conversation.mark_context_refreshed()

    agent = HealthAgent()
    try:
        reply = agent.chat(current_user.id, message, conversation)
    except Exception:
        logger.exception("chat_agent_failed user_id=%s", current_user.id)
        raise ValidationError("Failed to get response from AI assistant") from None
    return jsonify({"reply": reply})


@api.route("/chat/clear", methods=["POST"])
@login_required
def api_clear_chat():
    from agent.bot_message_repo import soft_clear_chat

    soft_clear_chat(current_user.id, WEB_CHAT_ID)
    return jsonify({"cleared": True})
