#!/usr/bin/env python3
import os
import sys

from sqlalchemy import select

from config_loader import get_threshold
from database import SessionLocal, init_db
from logging_config import configure_logging, get_logger
from models import User, UserCredentials, UserSettings
from security import encrypt_data_for_user, get_password_hash, validate_password

configure_logging()
logger = get_logger(__name__)


def create_default_admin():
    """
    Create default admin user from environment variables.
    Idempotent - can be run multiple times safely.
    """
    admin_username = os.getenv("ADMIN_USERNAME")
    admin_password = os.getenv("ADMIN_PASSWORD")

    garmin_email = os.getenv("GARMIN_EMAIL", "")
    garmin_password = os.getenv("GARMIN_PASSWORD", "")
    hevy_api_key = os.getenv("HEVY_API_KEY", "")

    if not admin_username or not admin_password:
        logger.error(
            "ADMIN_USERNAME and ADMIN_PASSWORD environment variables are required"
        )
        logger.error("Please set these in your .env file or Kubernetes secrets")
        sys.exit(1)

    is_valid, message = validate_password(admin_password)
    if not is_valid:
        logger.error(f"Admin password validation failed: {message}")
        sys.exit(1)

    db = SessionLocal()
    try:
        admin = db.scalars(select(User).where(User.username == admin_username)).first()

        if admin:
            logger.info(f"Admin user already exists: {admin_username}")

            if any([garmin_email, garmin_password, hevy_api_key]):
                _update_admin_credentials(
                    db, admin.id, garmin_email, garmin_password, hevy_api_key
                )

            return admin.id

        logger.info(f"Creating default admin user: {admin_username}")
        admin = User(
            username=admin_username, password_hash=get_password_hash(admin_password)
        )
        db.add(admin)
        db.commit()  # Commit user first - required before encrypt_data_for_user

        admin_id = admin.id  # Save ID (object may detach after other sessions commit)

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
            f"✅ Successfully created admin user: {admin_username} (ID: {admin_id})"
        )

        if garmin_email:
            logger.info("  ✅ Garmin credentials configured")
        if hevy_api_key:
            logger.info("  ✅ Hevy API key configured")

        return admin_id

    except Exception as e:
        logger.error(f"Failed to create admin user: {e}")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


def _create_admin_credentials(db, user_id, garmin_email, garmin_password, hevy_api_key):
    """Create encrypted credentials for admin user"""
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
    logger.info(f"Created credentials for admin user {user_id}")


def _update_admin_credentials(db, user_id, garmin_email, garmin_password, hevy_api_key):
    """Update existing admin credentials (idempotent)"""
    creds = db.scalars(
        select(UserCredentials).where(UserCredentials.user_id == user_id)
    ).first()

    if not creds:
        _create_admin_credentials(
            db, user_id, garmin_email, garmin_password, hevy_api_key
        )
        return

    updated = False
    if garmin_email and garmin_email != creds.garmin_email:
        creds.garmin_email = garmin_email
        updated = True
        logger.info(f"Updated Garmin email for user {user_id}")

    if garmin_password:
        creds.encrypted_garmin_password = encrypt_data_for_user(
            garmin_password, user_id
        )
        updated = True
        logger.info(f"Updated Garmin password for user {user_id}")

    if hevy_api_key:
        creds.encrypted_hevy_api_key = encrypt_data_for_user(hevy_api_key, user_id)
        updated = True
        logger.info(f"Updated Hevy API key for user {user_id}")

    if updated:
        db.commit()
        logger.info(f"✅ Credentials updated for user {user_id}")


if __name__ == "__main__":
    logger.info("🔐 Bootstrapping default admin user...")
    init_db()
    create_default_admin()
    logger.info("✅ Bootstrap complete")
