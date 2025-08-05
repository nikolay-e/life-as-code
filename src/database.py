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
from sqlalchemy.orm import Session, scoped_session, sessionmaker

from models import Base

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL")

# If DATABASE_URL is not set, construct it from individual components
if not DATABASE_URL:
    POSTGRES_USER = os.getenv("POSTGRES_USER")
    POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
    POSTGRES_DB = os.getenv("POSTGRES_DB")
    POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")

    if not all([POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB]):
        raise ValueError(
            "DATABASE_URL or individual postgres environment variables (POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB) must be set"
        )

    DATABASE_URL = f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
    logger.info(
        f"Constructed DATABASE_URL from environment variables for host: {POSTGRES_HOST}"
    )

if not DATABASE_URL:
    raise ValueError("Could not determine database connection parameters")

# Create engine with connection pooling
engine = create_engine(
    DATABASE_URL,
    pool_size=20,  # Increased from 10 to handle more concurrent connections
    max_overflow=30,  # Increased from 20 for burst capacity
    pool_pre_ping=True,  # Validate connections before use
    pool_recycle=3600,  # Recycle connections every hour to prevent staleness
    echo=False,  # Set to True for SQL query logging in development
)

# Create thread-safe session factory
session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
SessionLocal = scoped_session(session_factory)


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
    """Get a new database session. Remember to call SessionLocal.remove() after use in background threads."""
    return SessionLocal()


@contextmanager
def get_db_session_context() -> Generator[Session, None, None]:
    """
    Context manager for database sessions.
    Automatically handles commit/rollback and session cleanup.
    Uses scoped session for thread safety.

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
        # Clean up the scoped session for this thread
        SessionLocal.remove()


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


def get_counts_for_models(user_id: int, models_list: list) -> dict:
    """Get record counts for specified models for a user in a single query batch."""
    counts = {}
    try:
        with get_db_session_context() as db:
            # Batch all count queries into a single transaction
            for model_class, key in models_list:
                count = db.scalar(
                    select(func.count())
                    .select_from(model_class)
                    .filter(model_class.user_id == user_id)
                )
                counts[key] = count

        return counts
    except SQLAlchemyError as e:
        logger.error(f"Error getting model counts for user {user_id}: {e}")
        return {}


def get_table_counts_for_user(user_id: int) -> dict:
    """Get record counts for all main tables for a specific user."""
    from models import HRV, Energy, HeartRate, Sleep, Steps, Stress, Weight, WorkoutSet

    models_list = [
        (Sleep, "sleep"),
        (HRV, "hrv"),
        (Weight, "weight"),
        (HeartRate, "heart_rate"),
        (Stress, "stress"),
        (Steps, "steps"),
        (Energy, "energy"),
        (WorkoutSet, "workout_sets"),
    ]

    return get_counts_for_models(user_id, models_list)


def bulk_upsert_records(
    records: list, model_class, unique_fields: list, user_id: int
) -> dict:
    """
    Bulk upsert records for better performance.

    Args:
        records: List of dictionaries or Pydantic models to upsert
        model_class: SQLAlchemy model class
        unique_fields: Fields that make a record unique
        user_id: User ID for all records

    Returns:
        dict: Summary of operation results
    """
    result = {"created": 0, "updated": 0, "errors": 0}

    try:
        with get_db_session_context() as db:
            for record_data in records:
                try:
                    # Convert Pydantic model to dict if necessary
                    if hasattr(record_data, "model_dump"):
                        data_dict = record_data.model_dump(exclude_none=True)
                    else:
                        data_dict = record_data.copy()

                    # Add user_id
                    data_dict["user_id"] = user_id

                    # Build query to find existing record
                    query = select(model_class).where(model_class.user_id == user_id)
                    for field in unique_fields:
                        if field in data_dict:
                            query = query.where(
                                getattr(model_class, field) == data_dict[field]
                            )

                    existing = db.scalars(query).first()

                    if existing:
                        # Update existing record
                        for key, value in data_dict.items():
                            if hasattr(existing, key) and value is not None:
                                setattr(existing, key, value)
                        result["updated"] += 1
                    else:
                        # Create new record
                        new_record = model_class(**data_dict)
                        db.add(new_record)
                        result["created"] += 1

                except Exception as e:
                    logger.error(f"Error processing record: {e}")
                    result["errors"] += 1
                    continue

        logger.info(f"Bulk upsert completed: {result}")
        return result

    except SQLAlchemyError as e:
        logger.error(f"Error in bulk upsert: {e}")
        return {"error": str(e)}


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
