import os
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from models import HRV, Sleep, User


class TestUserModel:
    def test_create_user(self, db_session):
        from security import get_password_hash

        user = User(
            username="model-test@example.com",
            password_hash=get_password_hash("password123"),
        )
        db_session.add(user)
        db_session.commit()
        assert user.id is not None

    def test_unique_username(self, db_session):
        from security import get_password_hash

        user1 = User(username="dup@test.com", password_hash=get_password_hash("pass1"))
        db_session.add(user1)
        db_session.commit()

        user2 = User(username="dup@test.com", password_hash=get_password_hash("pass2"))
        db_session.add(user2)
        with pytest.raises(Exception):
            db_session.commit()
        db_session.rollback()


class TestHealthDataModels:
    def test_sleep_creation(self, db_session, test_user):
        sleep = Sleep(
            user_id=test_user.id,
            date=date(2024, 1, 1),
            source="garmin",
            total_sleep_minutes=450,
            deep_minutes=90,
        )
        db_session.add(sleep)
        db_session.commit()
        assert sleep.id is not None
        assert sleep.updated_at is not None

    def test_different_sources_same_date(self, db_session, test_user):
        sleep_garmin = Sleep(
            user_id=test_user.id,
            date=date(2024, 1, 1),
            source="garmin",
            total_sleep_minutes=450,
        )
        sleep_whoop = Sleep(
            user_id=test_user.id,
            date=date(2024, 1, 1),
            source="whoop",
            total_sleep_minutes=440,
        )
        db_session.add_all([sleep_garmin, sleep_whoop])
        db_session.commit()
        assert sleep_garmin.id != sleep_whoop.id

    def test_hrv_creation(self, db_session, test_user):
        hrv = HRV(
            user_id=test_user.id,
            date=date(2024, 1, 1),
            source="garmin",
            hrv_avg=65.0,
        )
        db_session.add(hrv)
        db_session.commit()
        assert hrv.id is not None

    def test_cascade_delete(self, db_session):
        from security import get_password_hash

        user = User(
            username="cascade-test@example.com",
            password_hash=get_password_hash("pass"),
        )
        db_session.add(user)
        db_session.commit()
        uid = user.id

        sleep = Sleep(
            user_id=uid,
            date=date(2024, 1, 1),
            source="garmin",
            total_sleep_minutes=400,
        )
        db_session.add(sleep)
        db_session.commit()

        db_session.delete(user)
        db_session.commit()

        remaining = db_session.query(Sleep).filter_by(user_id=uid).all()
        assert len(remaining) == 0
