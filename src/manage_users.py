#!/usr/bin/env python3
"""
User Management Script for Life-as-Code
This script allows manual creation and management of user accounts.
Use this to add users to your private portal.
"""

import getpass
import os
import sys

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from config_loader import get_threshold
from database import SessionLocal, init_db
from models import User, UserCredentials, UserSettings
from security import (
    encrypt_data_for_user,
    get_password_hash,
    validate_password,
    validate_username,
)


def create_user():
    """Create a new user account."""
    print("🔐 Create New User Account")
    print("=" * 30)

    # Get username
    while True:
        username = input("Username (email recommended): ").strip()
        if not username:
            print("Username cannot be empty.")
            continue
        if not validate_username(username):
            print("Invalid username. Must be 3-80 characters, alphanumeric plus _.@-")
            continue
        break

    # Get password
    while True:
        password = getpass.getpass("Password: ")
        is_valid, message = validate_password(password)
        if not is_valid:
            print(f"❌ {message}")
            continue

        confirm_password = getpass.getpass("Confirm password: ")
        if password != confirm_password:
            print("❌ Passwords don't match.")
            continue
        break

    # Optional: Get Garmin credentials
    garmin_email = input("Garmin email (optional, can be set later): ").strip()
    garmin_password = ""
    if garmin_email:
        garmin_password = getpass.getpass("Garmin password (optional): ")

    # Optional: Get Hevy API key
    hevy_api_key = input("Hevy API key (optional, can be set later): ").strip()

    # Create user in database
    db = SessionLocal()
    try:
        # Check if user already exists
        existing_user = db.scalars(select(User).filter_by(username=username)).first()
        if existing_user:
            print(f"❌ User '{username}' already exists.")
            return False

        # Create new user
        user = User(username=username, password_hash=get_password_hash(password))
        db.add(user)
        db.flush()  # Get the user ID

        # Create credentials record
        credentials = UserCredentials(
            user_id=user.id,
            garmin_email=garmin_email if garmin_email else None,
            encrypted_garmin_password=(
                encrypt_data_for_user(garmin_password, user.id)
                if garmin_password
                else None
            ),
            encrypted_hevy_api_key=(
                encrypt_data_for_user(hevy_api_key, user.id) if hevy_api_key else None
            ),
        )
        db.add(credentials)

        # Create UserSettings with default values
        settings = UserSettings(
            user_id=user.id,
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
        print(f"✅ User '{username}' created successfully!")
        print(f"   User ID: {user.id}")

        if garmin_email:
            print(f"   Garmin email: {garmin_email}")
        if garmin_password:
            print("   Garmin password: [encrypted]")
        if hevy_api_key:
            print("   Hevy API key: [encrypted]")

        return True

    except IntegrityError:
        db.rollback()
        print(f"❌ User '{username}' already exists.")
        return False
    except Exception as e:
        db.rollback()
        print(f"❌ Error creating user: {e}")
        return False
    finally:
        db.close()


def list_users():
    """List all users."""
    db = SessionLocal()
    try:
        users = db.scalars(select(User)).all()
        if not users:
            print("No users found.")
            return

        print("\n👥 User List")
        print("=" * 20)
        for user in users:
            creds = db.scalars(
                select(UserCredentials).filter_by(user_id=user.id)
            ).first()
            print(f"ID: {user.id}")
            print(f"Username: {user.username}")
            print(f"Created: {user.created_at.strftime('%Y-%m-%d %H:%M')}")
            if creds:
                print(f"Garmin: {'✅' if creds.encrypted_garmin_password else '❌'}")
                print(f"Hevy: {'✅' if creds.encrypted_hevy_api_key else '❌'}")
            print("-" * 20)
    finally:
        db.close()


def delete_user():
    """Delete a user account."""
    print("\n🗑️ Delete User Account")
    print("=" * 25)

    username = input("Username to delete: ").strip()
    if not username:
        print("Username cannot be empty.")
        return

    # Confirm deletion
    confirm = input(
        f"Are you sure you want to delete '{username}'? (type 'DELETE' to confirm): "
    )
    if confirm != "DELETE":
        print("Deletion cancelled.")
        return

    db = SessionLocal()
    try:
        user = db.scalars(select(User).filter_by(username=username)).first()
        if not user:
            print(f"❌ User '{username}' not found.")
            return

        # Store user ID for token cleanup
        user_id = user.id

        # Delete user (cascade will handle credentials and data)
        db.delete(user)
        db.commit()

        # Clean up Garmin tokens directory
        import shutil

        token_dir = f"/app/.garminconnect/user_{user_id}"
        if os.path.exists(token_dir):
            try:
                shutil.rmtree(token_dir)
                print(f"🧹 Cleaned up Garmin tokens for user {user_id}")
            except Exception as e:
                print(f"⚠️ Warning: Could not clean up token directory: {e}")

        print(f"✅ User '{username}' deleted successfully!")

    except Exception as e:
        db.rollback()
        print(f"❌ Error deleting user: {e}")
    finally:
        db.close()


def update_credentials():
    """Update user credentials."""
    print("\n🔑 Update User Credentials")
    print("=" * 28)

    username = input("Username: ").strip()
    if not username:
        print("Username cannot be empty.")
        return

    db = SessionLocal()
    try:
        user = db.scalars(select(User).filter_by(username=username)).first()
        if not user:
            print(f"❌ User '{username}' not found.")
            return

        creds = db.query(UserCredentials).filter_by(user_id=user.id).first()
        if not creds:
            print(f"❌ Credentials record not found for '{username}'.")
            return

        print(f"Updating credentials for: {username}")
        print("(Press Enter to skip/keep current value)")

        # Update Garmin credentials
        garmin_email = input(
            f"Garmin email [{creds.garmin_email or 'not set'}]: "
        ).strip()
        if garmin_email:
            creds.garmin_email = garmin_email

        garmin_password = getpass.getpass("Garmin password [hidden]: ")
        if garmin_password:
            creds.encrypted_garmin_password = encrypt_data_for_user(
                garmin_password, user.id
            )

        # Update Hevy API key
        hevy_api_key = input("Hevy API key [hidden]: ").strip()
        if hevy_api_key:
            creds.encrypted_hevy_api_key = encrypt_data_for_user(hevy_api_key, user.id)

        db.commit()
        print(f"✅ Credentials updated for '{username}'!")

    except Exception as e:
        db.rollback()
        print(f"❌ Error updating credentials: {e}")
    finally:
        db.close()


def main():
    """Main menu."""
    # Initialize database
    init_db()

    while True:
        print("\n🔐 Life-as-Code User Management")
        print("=" * 35)
        print("1. Create new user")
        print("2. List all users")
        print("3. Update user credentials")
        print("4. Delete user")
        print("5. Exit")

        choice = input("\nSelect option (1-5): ").strip()

        if choice == "1":
            create_user()
        elif choice == "2":
            list_users()
        elif choice == "3":
            update_credentials()
        elif choice == "4":
            delete_user()
        elif choice == "5":
            print("Goodbye!")
            sys.exit(0)
        else:
            print("❌ Invalid option. Please try again.")


if __name__ == "__main__":
    main()
