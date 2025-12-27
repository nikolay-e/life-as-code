import datetime
import os
from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, scoped_session, sessionmaker

from logging_config import get_logger, init_db_event_logging, init_slow_query_logging

logger = get_logger(__name__)

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
    hide_parameters=True,  # Hide sensitive parameters in error logs
)

# Initialize database event logging (slow queries, connection pool)
init_slow_query_logging(engine)
init_db_event_logging(engine)

# Create thread-safe session factory
session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
SessionLocal = scoped_session(session_factory)


def init_db() -> None:
    try:
        from models import Base

        # Check if alembic_version table exists (indicates migrations are being used)
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT EXISTS ("
                    "SELECT FROM information_schema.tables "
                    "WHERE table_name = 'alembic_version'"
                    ")"
                )
            )
            has_alembic = result.scalar()

        if has_alembic:
            logger.info("Alembic migrations detected - skipping create_all()")
            return

        # Only use create_all for fresh databases without Alembic
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created via create_all()")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise


def get_db_session() -> Session:
    return SessionLocal()


@contextmanager
def get_db_session_context() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
        logger.debug("transaction_committed")
    except Exception as e:
        db.rollback()
        logger.error(
            "transaction_rollback",
            error_type=type(e).__name__,
        )
        raise
    finally:
        db.close()
        SessionLocal.remove()


@contextmanager
def get_independent_session() -> Generator[Session, None, None]:
    db = session_factory()
    try:
        yield db
        db.commit()
        logger.debug("independent_transaction_committed")
    except Exception as e:
        db.rollback()
        logger.error(
            "independent_transaction_rollback",
            error_type=type(e).__name__,
        )
        raise
    finally:
        db.close()


def check_db_connection() -> bool:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        logger.info("✅ Database connection is healthy")
        return True
    except SQLAlchemyError as e:
        logger.error(f"❌ Database connection failed: {e}")
        return False


def get_table_counts() -> dict:
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
    from sqlalchemy.dialects.postgresql import insert

    if not records:
        return {"created": 0, "updated": 0, "errors": 0}

    result = {"created": 0, "updated": 0, "errors": 0}

    try:
        with get_db_session_context() as db:
            # Convert all records to dicts and add user_id
            processed_records = []
            all_keys: set[str] = set()

            for record_data in records:
                try:
                    if hasattr(record_data, "model_dump"):
                        data_dict = record_data.model_dump()
                    else:
                        data_dict = record_data.copy()

                    data_dict["user_id"] = user_id
                    if "created_at" not in data_dict:
                        data_dict["created_at"] = datetime.datetime.utcnow()

                    all_keys.update(data_dict.keys())
                    processed_records.append(data_dict)
                except Exception as e:
                    logger.error(f"Error processing record: {e}")
                    result["errors"] += 1

            if not processed_records:
                return result

            for record in processed_records:
                for key in all_keys:
                    if key not in record:
                        record[key] = None

            # Build INSERT statement with ON CONFLICT
            stmt = insert(model_class).values(processed_records)

            # ON CONFLICT clause: update on conflict
            conflict_columns = ["user_id"] + unique_fields
            update_dict = {
                col: getattr(stmt.excluded, col)
                for col in processed_records[0].keys()
                if col not in ["id", "created_at", "user_id"]
            }

            stmt = stmt.on_conflict_do_update(
                index_elements=conflict_columns, set_=update_dict
            )

            db.execute(stmt)
            result["created"] = len(processed_records)

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
