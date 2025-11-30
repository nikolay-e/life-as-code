import logging
import threading
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import select

from config import APP_VERSION, BUILD_DATE, VCS_REF, get_commit_short
from data_loaders import get_workout_volume_data, load_data_for_user
from database import get_db_session_context
from models import DataSync, User, UserCredentials, UserSettings
from routes import UserModel
from security import decrypt_data_for_user, encrypt_data_for_user, verify_password

api = Blueprint("api", __name__, url_prefix="/api")
logger = logging.getLogger(__name__)


@api.route("/version")
def get_version():
    return jsonify(
        {
            "version": APP_VERSION,
            "buildDate": BUILD_DATE,
            "commit": get_commit_short(),
            "commitFull": VCS_REF,
        }
    )


@api.route("/auth/login", methods=["POST"])
def api_login():
    data = request.get_json()
    if not data:
        return jsonify({"message": "Invalid request"}), 400

    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"message": "Username and password required"}), 400

    try:
        with get_db_session_context() as db:
            user = db.scalars(select(User).filter_by(username=username)).first()
            if user and verify_password(password, user.password_hash):
                user_model = UserModel(user.id, user.username)
                login_user(user_model)
                return jsonify({"user": {"id": user.id, "username": user.username}})
            return jsonify({"message": "Invalid username or password"}), 401
    except Exception:
        return jsonify({"message": "An error occurred during login"}), 500


@api.route("/auth/logout", methods=["POST"])
@login_required
def api_logout():
    logout_user()
    return jsonify({"message": "Logged out"})


@api.route("/auth/me", methods=["GET"])
def api_me():
    if current_user.is_authenticated:
        return jsonify(
            {"user": {"id": current_user.id, "username": current_user.username}}
        )
    return jsonify({"message": "Not authenticated"}), 401


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
            start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError as e:
            logger.error(f"Invalid date format: {e}")
            return jsonify({"error": "Invalid date format. Use YYYY-MM-DD"}), 400

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
                    result[key] = volume_df.to_dict(orient="records")
            else:
                df["date"] = df["date"].astype(str)
                result[key] = df.to_dict(orient="records")

    return jsonify(result)


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
    data = request.get_json()
    if not data:
        return jsonify({"message": "Invalid request"}), 400

    with get_db_session_context() as db:
        settings = db.scalars(
            select(UserSettings).filter_by(user_id=current_user.id)
        ).first()

        if not settings:
            settings = UserSettings(user_id=current_user.id)
            db.add(settings)

        if "hrv_good_threshold" in data:
            settings.hrv_good_threshold = data["hrv_good_threshold"]
        if "hrv_moderate_threshold" in data:
            settings.hrv_moderate_threshold = data["hrv_moderate_threshold"]
        if "deep_sleep_good_threshold" in data:
            settings.deep_sleep_good_threshold = data["deep_sleep_good_threshold"]
        if "deep_sleep_moderate_threshold" in data:
            settings.deep_sleep_moderate_threshold = data[
                "deep_sleep_moderate_threshold"
            ]
        if "total_sleep_good_threshold" in data:
            settings.total_sleep_good_threshold = data["total_sleep_good_threshold"]
        if "total_sleep_moderate_threshold" in data:
            settings.total_sleep_moderate_threshold = data[
                "total_sleep_moderate_threshold"
            ]
        if "training_high_volume_threshold" in data:
            settings.training_high_volume_threshold = data[
                "training_high_volume_threshold"
            ]

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
    with get_db_session_context() as db:
        creds = db.scalars(
            select(UserCredentials).filter_by(user_id=current_user.id)
        ).first()

        if not creds:
            return jsonify({"garmin_email": "", "hevy_api_key": ""})

        hevy_key = ""
        if creds.encrypted_hevy_api_key:
            try:
                hevy_key = decrypt_data_for_user(
                    creds.encrypted_hevy_api_key, current_user.id
                )
            except Exception:
                hevy_key = ""

        return jsonify(
            {
                "garmin_email": creds.garmin_email or "",
                "hevy_api_key": hevy_key[:8] + "..." if hevy_key else "",
            }
        )


@api.route("/settings/credentials", methods=["PUT"])
@login_required
def api_save_credentials():
    data = request.get_json()
    if not data:
        return jsonify({"message": "Invalid request"}), 400

    with get_db_session_context() as db:
        creds = db.scalars(
            select(UserCredentials).filter_by(user_id=current_user.id)
        ).first()

        if not creds:
            creds = UserCredentials(user_id=current_user.id)
            db.add(creds)

        if "garmin_email" in data:
            creds.garmin_email = data["garmin_email"]

        if "garmin_password" in data and data["garmin_password"]:
            creds.encrypted_garmin_password = encrypt_data_for_user(
                data["garmin_password"], current_user.id
            )

        if "hevy_api_key" in data and data["hevy_api_key"]:
            creds.encrypted_hevy_api_key = encrypt_data_for_user(
                data["hevy_api_key"], current_user.id
            )

        db.commit()

        return jsonify({"message": "Credentials saved"})


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
                    "records_synced": s.records_synced,
                    "status": s.status,
                    "error_message": s.error_message,
                }
                for s in syncs
            ]
        )


@api.route("/sync/garmin", methods=["POST"])
@login_required
def api_sync_garmin():
    user_id = current_user.id

    def run_sync():
        from pull_garmin_data import sync_garmin_data_for_user

        sync_garmin_data_for_user(user_id)

    thread = threading.Thread(target=run_sync, daemon=True)
    thread.start()

    return jsonify({"message": "Garmin sync started"})


@api.route("/sync/hevy", methods=["POST"])
@login_required
def api_sync_hevy():
    user_id = current_user.id

    def run_sync():
        from pull_hevy_data import sync_hevy_data_for_user

        sync_hevy_data_for_user(user_id)

    thread = threading.Thread(target=run_sync, daemon=True)
    thread.start()

    return jsonify({"message": "Heavy sync started"})
