#!/usr/bin/env python3
"""
Quick script to create a test user with credentials from .env
"""

import os

from config import (
    HRV_THRESHOLDS,
    SLEEP_THRESHOLDS,
    TOTAL_SLEEP_THRESHOLDS,
    TRAINING_THRESHOLDS,
)
from database import SessionLocal, init_db
from models import User, UserCredentials, UserSettings
from security import encrypt_data_for_user, get_password_hash


def create_test_user():
    # Ensure database is initialized
    init_db()

    # Get credentials from env
    garmin_email = os.getenv("EMAIL", "dbhbpjptv@gmail.com")
    garmin_password = os.getenv("PASSWORD", "ynWQ9VxpFHuLzFaZvJcN")
    hevy_api_key = os.getenv("HEVY_API_KEY", "6c62bac8-47da-40cd-82b0-b4e39e0eb899")

    print("🔐 Creating test user with .env credentials...")
    print("=" * 50)

    db = SessionLocal()
    try:
        # Check if user already exists
        existing_user = db.query(User).filter_by(username="testuser").first()
        if existing_user:
            print('❌ User "testuser" already exists')
            return False

        # Create new user
        user = User(username="testuser", password_hash=get_password_hash("testpass123"))
        db.add(user)
        db.flush()  # Get the user ID

        print(f"✅ Created user: testuser (ID: {user.id})")

        # Create credentials with env values
        credentials = UserCredentials(
            user_id=user.id,
            garmin_email=garmin_email,
            encrypted_garmin_password=encrypt_data_for_user(garmin_password, user.id),
            encrypted_hevy_api_key=encrypt_data_for_user(hevy_api_key, user.id),
        )
        db.add(credentials)

        # Create default settings
        settings = UserSettings(
            user_id=user.id,
            hrv_good_threshold=HRV_THRESHOLDS.get("good", 45),
            hrv_moderate_threshold=HRV_THRESHOLDS.get("moderate", 35),
            deep_sleep_good_threshold=SLEEP_THRESHOLDS.get("good", 90),
            deep_sleep_moderate_threshold=SLEEP_THRESHOLDS.get("moderate", 60),
            total_sleep_good_threshold=TOTAL_SLEEP_THRESHOLDS.get("good", 7.5),
            total_sleep_moderate_threshold=TOTAL_SLEEP_THRESHOLDS.get("moderate", 6.5),
            training_high_volume_threshold=TRAINING_THRESHOLDS.get(
                "high_volume_kg", 5000
            ),
        )
        db.add(settings)

        db.commit()

        print("✅ User created successfully!")
        print("-" * 30)
        print("Username: testuser")
        print("Password: testpass123")
        print(f"Garmin email: {garmin_email}")
        print("Garmin password: [encrypted with per-user key]")
        print("Hevy API key: [encrypted with per-user key]")
        print("-" * 30)
        print("🚀 You can now login at http://localhost:8050/login")

        return True

    except Exception as e:
        db.rollback()
        print(f"❌ Error creating user: {e}")
        return False
    finally:
        db.close()


if __name__ == "__main__":
    create_test_user()
