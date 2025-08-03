"""
Database connection and session management for Life-as-Code.
Handles PostgreSQL connections using SQLAlchemy.
"""

import logging
import os
from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from models import Base

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable not set")

# Create engine with connection pooling
engine = create_engine(
    DATABASE_URL,
    pool_size=20,  # Increased from 10 to handle more concurrent connections
    max_overflow=30,  # Increased from 20 for burst capacity
    pool_pre_ping=True,  # Validate connections before use
    pool_recycle=3600,  # Recycle connections every hour to prevent staleness
    echo=False,  # Set to True for SQL query logging in development
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """Initialize the database by creating all tables."""
    try:
        logger.info("Initializing database tables...")
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Database initialization completed successfully")
    except SQLAlchemyError as e:
        logger.error(f"❌ Database initialization failed: {e}")
        raise


def get_db_session() -> Session:
    """Get a new database session."""
    return SessionLocal()


@contextmanager
def get_db_session_context() -> Generator[Session, None, None]:
    """
    Context manager for database sessions.
    Automatically handles commit/rollback and session cleanup.

    Usage:
        with get_db_session_context() as db:
            # Do database operations
            db.add(new_record)
            # Commit happens automatically on success
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Database session error: {e}")
        raise
    finally:
        db.close()


def check_db_connection() -> bool:
    """Check if database connection is working."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        logger.info("✅ Database connection is healthy")
        return True
    except SQLAlchemyError as e:
        logger.error(f"❌ Database connection failed: {e}")
        return False


def get_table_counts() -> dict:
    """Get record counts for all main tables."""
    counts = {}
    try:
        with get_db_session_context() as db:
            from models import HRV, DataSync, HeartRate, Sleep, Weight, WorkoutSet

            counts["sleep"] = db.scalar(select(func.count()).select_from(Sleep))
            counts["hrv"] = db.scalar(select(func.count()).select_from(HRV))
            counts["weight"] = db.scalar(select(func.count()).select_from(Weight))
            counts["heart_rate"] = db.scalar(
                select(func.count()).select_from(HeartRate)
            )
            counts["workout_sets"] = db.scalar(
                select(func.count()).select_from(WorkoutSet)
            )
            counts["data_sync"] = db.scalar(select(func.count()).select_from(DataSync))

        return counts
    except SQLAlchemyError as e:
        logger.error(f"Error getting table counts: {e}")
        return {}


def get_table_counts_for_user(user_id: int) -> dict:
    """Get record counts for all main tables for a specific user."""
    counts = {}
    try:
        with get_db_session_context() as db:
            from models import HRV, HeartRate, Sleep, Weight, WorkoutSet

            counts["sleep"] = db.scalar(
                select(func.count()).select_from(Sleep).filter(Sleep.user_id == user_id)
            )
            counts["hrv"] = db.scalar(
                select(func.count()).select_from(HRV).filter(HRV.user_id == user_id)
            )
            counts["weight"] = db.scalar(
                select(func.count())
                .select_from(Weight)
                .filter(Weight.user_id == user_id)
            )
            counts["heart_rate"] = db.scalar(
                select(func.count())
                .select_from(HeartRate)
                .filter(HeartRate.user_id == user_id)
            )
            counts["workout_sets"] = db.scalar(
                select(func.count())
                .select_from(WorkoutSet)
                .filter(WorkoutSet.user_id == user_id)
            )

        return counts
    except SQLAlchemyError as e:
        logger.error(f"Error getting user table counts: {e}")
        return {}


if __name__ == "__main__":
    # Test database connection and initialization
    print("Testing database connection...")

    if check_db_connection():
        init_db()
        counts = get_table_counts()
        print("\nCurrent table record counts:")
        for table, count in counts.items():
            print(f"  {table}: {count} records")
    else:
        print("Failed to connect to database")
