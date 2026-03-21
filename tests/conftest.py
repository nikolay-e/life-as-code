import os
import sys
from datetime import date, timedelta

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing-only-32chars")  # pragma: allowlist secret
os.environ.setdefault(
    "FERNET_KEY",
    "54BnS4pmP4MQBDxKfAIZ1PJ0SMH01c58kdpPv1q0YC8=",  # pragma: allowlist secret
)
os.environ.setdefault("ADMIN_USERNAME", "admin@test.com")
os.environ.setdefault("ADMIN_PASSWORD", "test-admin-password-123")  # pragma: allowlist secret
os.environ.setdefault("POSTGRES_PASSWORD", "testpass")  # pragma: allowlist secret
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg2://life_as_code_user:testpass@localhost:5434/life_as_code_test",  # pragma: allowlist secret
)

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from models import Base, User


@pytest.fixture(scope="session")
def db_engine():
    url = os.getenv(
        "TEST_DATABASE_URL",
        "postgresql+psycopg2://life_as_code_user:testpass@localhost:5434/life_as_code_test",  # pragma: allowlist secret
    )
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db_session(db_engine):
    connection = db_engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection)()
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def test_user(db_session):
    from security import get_password_hash

    user = User(
        username="test@example.com",
        password_hash=get_password_hash("test-password-123"),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def make_data_points():
    from analytics.types import DataPoint

    def _make(days=30, base_value=50.0, noise=5.0, ref_date=None):
        import random

        end = ref_date or date.today()
        random.seed(42)
        return [
            DataPoint(
                date=(end - timedelta(days=days - 1 - i)).isoformat(),
                value=base_value + random.uniform(-noise, noise),
            )
            for i in range(days)
        ]

    return _make
