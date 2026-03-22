#!/usr/bin/env python3
import os
import sys

from sqlalchemy import select

from config_loader import get_threshold
from database import SessionLocal, init_db
from logging_config import configure_logging, get_logger
from models import User, UserCredentials, UserSettings
from security import encrypt_data_for_user, get_password_hash

configure_logging()
logger = get_logger(__name__)


def create_default_admin():
    admin_username = os.getenv("ADMIN_USERNAME")
    admin_password = os.getenv("ADMIN_PASSWORD")

    garmin_email = os.getenv("GARMIN_EMAIL", "")
    garmin_password = os.getenv("GARMIN_PASSWORD", "")
    hevy_api_key = os.getenv("HEVY_API_KEY", "")

    if not admin_username or not admin_password:
        logger.error(
            "ADMIN_USERNAME and ADMIN_PASSWORD environment variables are required"
        )
        sys.exit(1)

    db = SessionLocal()
    try:
        admin = db.scalars(select(User).where(User.username == admin_username)).first()

        if admin:
            logger.info("admin_user_exists", username=admin_username)

            existing_creds = db.scalars(
                select(UserCredentials).where(UserCredentials.user_id == admin.id)
            ).first()
            if not existing_creds and any(
                [garmin_email, garmin_password, hevy_api_key]
            ):
                _create_admin_credentials(
                    db, admin.id, garmin_email, garmin_password, hevy_api_key
                )
                db.commit()
            elif existing_creds:
                logger.info("admin_credentials_exist_skipping_env", user_id=admin.id)

            return admin.id

        logger.info("creating_admin_user", username=admin_username)
        admin = User(
            username=admin_username, password_hash=get_password_hash(admin_password)
        )
        db.add(admin)
        db.commit()

        admin_id = admin.id

        if any([garmin_email, garmin_password, hevy_api_key]):
            _create_admin_credentials(
                db, admin_id, garmin_email, garmin_password, hevy_api_key
            )

        settings = UserSettings(
            user_id=admin_id,
            hrv_good_threshold=get_threshold("hrv.good", 45),
            hrv_moderate_threshold=get_threshold("hrv.moderate", 35),
            deep_sleep_good_threshold=get_threshold("sleep.deep_sleep.good", 90),
            deep_sleep_moderate_threshold=get_threshold(
                "sleep.deep_sleep.moderate", 60
            ),
            total_sleep_good_threshold=get_threshold("sleep.total_sleep.good", 7.5),
            total_sleep_moderate_threshold=get_threshold(
                "sleep.total_sleep.moderate", 6.5
            ),
            training_high_volume_threshold=get_threshold("training.high_volume", 5000),
        )
        db.add(settings)

        db.commit()
        logger.info(
            "admin_user_created",
            username=admin_username,
            user_id=admin_id,
            garmin_configured=bool(garmin_email),
            hevy_configured=bool(hevy_api_key),
        )

        return admin_id

    except Exception as e:
        logger.error("admin_user_creation_failed", error=str(e))
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


def _create_admin_credentials(db, user_id, garmin_email, garmin_password, hevy_api_key):
    creds = UserCredentials(
        user_id=user_id,
        garmin_email=garmin_email if garmin_email else None,
        encrypted_garmin_password=(
            encrypt_data_for_user(garmin_password, user_id) if garmin_password else None
        ),
        encrypted_hevy_api_key=(
            encrypt_data_for_user(hevy_api_key, user_id) if hevy_api_key else None
        ),
    )
    db.add(creds)
    logger.info("admin_credentials_created", user_id=user_id)


if __name__ == "__main__":
    logger.info("bootstrap_started")
    init_db()
    create_default_admin()
    logger.info("bootstrap_complete")
