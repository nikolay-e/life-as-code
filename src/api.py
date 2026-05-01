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
    HevyCredentialsRequest,
    InterventionCreate,
    InterventionUpdate,
    LoginRequest,
    ProfileUpdate,
    ThresholdSettings,
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
    ClinicalAlertEvent,
    DataSync,
    FunctionalTest,
    GarminRacePrediction,
    Intervention,
    LongevityGoal,
    User,
    UserCredentials,
    UserSettings,
)
from pull_whoop_data import refresh_whoop_token_for_user
from routes import UserModel
from security import encrypt_data_for_user, verify_password
from settings import get_settings
from sync_manager import is_sync_in_progress
from utils import get_user_credentials

api = Blueprint("api", __name__, url_prefix="/api")
logger = get_logger(__name__)
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
    for record in records:
        for key, value in record.items():
            if isinstance(value, float) and not math.isfinite(value):
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
        "garmin_email_hint": _mask_email(creds.garmin_email if creds else None),
        "hevy_configured": bool(creds and creds.encrypted_hevy_api_key),
        "hevy_api_key_hint": _mask_api_key(
            creds.encrypted_hevy_api_key if creds else None
        ),
        "whoop_configured": whoop_has_token and not whoop_token_expired,
        "whoop_token_expired": whoop_token_expired,
        "whoop_auth_url": whoop_auth_url,
        "eight_sleep_configured": bool(
            creds and creds.eight_sleep_email and creds.encrypted_eight_sleep_password
        ),
        "eight_sleep_email_hint": _mask_email(
            creds.eight_sleep_email if creds else None
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

        creds.garmin_email = body.email
        creds.encrypted_garmin_password = encrypted_password

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

        creds.encrypted_hevy_api_key = encrypted_key

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
            creds.garmin_email = None
            creds.encrypted_garmin_password = None

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
            creds.encrypted_hevy_api_key = None

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

        creds.eight_sleep_email = body.email
        creds.encrypted_eight_sleep_password = encrypted_password
        creds.encrypted_eight_sleep_access_token = None
        creds.eight_sleep_token_expires_at = None

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
            creds.eight_sleep_email = None
            creds.encrypted_eight_sleep_password = None
            creds.encrypted_eight_sleep_access_token = None
            creds.eight_sleep_token_expires_at = None

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
                    if settings and settings.birth_date
                    else None
                ),
                "gender": settings.gender if settings else None,
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
            settings.birth_date = body.birth_date
        if "gender" in body.model_fields_set:
            settings.gender = body.gender

        db.commit()
        return jsonify(
            {
                "birth_date": (
                    settings.birth_date.isoformat() if settings.birth_date else None
                ),
                "gender": settings.gender,
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
        row.status = body.status
        now = utcnow()
        if body.status == "acknowledged" and row.acknowledged_at is None:
            row.acknowledged_at = now
        elif body.status == "resolved" and row.resolved_at is None:
            row.resolved_at = now
        db.commit()
        return jsonify(_serialize_model(row, CLINICAL_ALERT_FIELDS))
