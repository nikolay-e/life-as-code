import os
from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, scoped_session, sessionmaker

from date_utils import utcnow
from logging_config import get_logger, init_db_event_logging, init_slow_query_logging

logger = get_logger(__name__)

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL")

# If DATABASE_URL is not set, construct it from individual components
if not DATABASE_URL:
    POSTGRES_USER = os.getenv("POSTGRES_USER")
    POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
    POSTGRES_DB = os.getenv("POSTGRES_DB") or os.getenv("DB_NAME")
    POSTGRES_HOST = os.getenv("POSTGRES_HOST") or os.getenv("DB_HOST", "localhost")
    POSTGRES_PORT = os.getenv("POSTGRES_PORT") or os.getenv("DB_PORT", "5432")

    if not all([POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB]):
        raise ValueError(
            "DATABASE_URL or individual postgres environment variables (POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB/DB_NAME) must be set"
        )

    DATABASE_URL = f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
    logger.info("database_url_constructed", host=POSTGRES_HOST)

if not DATABASE_URL:
    raise ValueError("Could not determine database connection parameters")

# Create engine with connection pooling
engine = create_engine(
    DATABASE_URL,
    pool_size=20,  # Increased from 10 to handle more concurrent connections
    max_overflow=30,  # Increased from 20 for burst capacity
    pool_pre_ping=True,  # Validate connections before use
    pool_recycle=3600,  # Recycle connections every hour to prevent staleness
    pool_reset_on_return="rollback",  # Ensure clean state when returning to pool
    echo=False,  # Set to True for SQL query logging in development
    hide_parameters=True,  # Hide sensitive parameters in error logs
)

# Create read-only engine with AUTOCOMMIT for pandas queries
# This avoids transaction state issues in multi-threaded environments
read_engine = engine.execution_options(isolation_level="AUTOCOMMIT")

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
        logger.error("database_init_failed", error=str(e))
        raise


def get_db_session() -> Session:
    return SessionLocal()


@contextmanager
def get_db_session_context() -> Generator[Session]:
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
def get_independent_session() -> Generator[Session]:
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
        logger.error("database_connection_failed", error=str(e))
        return False


def bulk_upsert_records(
    records: list,
    model_class,
    unique_fields: list,
    user_id: int,
    source: str | None = None,
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
            model_columns = {c.name for c in model_class.__table__.columns}
            include_source = source is not None and "source" in model_columns

            for record_data in records:
                try:
                    if hasattr(record_data, "model_dump"):
                        data_dict = record_data.model_dump()
                    else:
                        data_dict = record_data.copy()

                    data_dict["user_id"] = user_id
                    if include_source:
                        data_dict["source"] = source
                    if "created_at" not in data_dict:
                        data_dict["created_at"] = utcnow()

                    all_keys.update(data_dict.keys())
                    processed_records.append(data_dict)
                except Exception as e:
                    logger.error("record_processing_error", error=str(e))
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
                if col not in ["id", "created_at", "user_id", "source"]
            }

            stmt = stmt.on_conflict_do_update(
                index_elements=conflict_columns, set_=update_dict
            )

            db.execute(stmt)
            result["created"] = len(processed_records)
            result["updated"] = 0

        logger.info(
            "bulk_upsert_completed",
            created=result["created"],
            updated=result.get("updated", 0),
            errors=result.get("errors", 0),
        )
        return result

    except SQLAlchemyError as e:
        logger.error("bulk_upsert_error", error=str(e))
        return {"error": str(e)}
