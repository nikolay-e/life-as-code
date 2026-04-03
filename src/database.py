from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, scoped_session, sessionmaker

from date_utils import utcnow
from logging_config import get_logger, init_db_event_logging, init_slow_query_logging
from settings import get_settings

logger = get_logger(__name__)

DATABASE_URL = get_settings().computed_database_url

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


def _to_record_dict(
    record_data,
    user_id: int,
    source: str | None,
    include_source: bool,
    all_keys: set[str],
    error_count_ref: list,
) -> "dict[str, Any] | None":
    try:
        data_dict: dict[str, Any] = (
            record_data.model_dump()
            if hasattr(record_data, "model_dump")
            else record_data.copy()
        )
        data_dict["user_id"] = user_id
        if include_source:
            data_dict["source"] = source
        if "created_at" not in data_dict:
            data_dict["created_at"] = utcnow()
        all_keys.update(data_dict.keys())
        return data_dict
    except Exception as e:
        logger.error("record_processing_error", error=str(e))
        error_count_ref[0] += 1
        return None


def _fill_missing_keys(records: list[dict], all_keys: set[str]) -> None:
    for record in records:
        for key in all_keys:
            if key not in record:
                record[key] = None


def _process_upsert_records(
    records: list,
    model_class,
    user_id: int,
    source: str | None,
    error_count_ref: list,
) -> list[dict]:
    model_columns = {c.name for c in model_class.__table__.columns}
    include_source = source is not None and "source" in model_columns
    all_keys: set[str] = set()
    processed: list[dict] = []
    for record_data in records:
        d = _to_record_dict(
            record_data, user_id, source, include_source, all_keys, error_count_ref
        )
        if d is not None:
            processed.append(d)
    _fill_missing_keys(processed, all_keys)
    return processed


def _build_upsert_stmt(model_class, processed_records: list[dict], unique_fields: list):
    from sqlalchemy import literal_column
    from sqlalchemy.dialects.postgresql import insert

    stmt = insert(model_class).values(processed_records)
    conflict_columns = ["user_id"] + unique_fields
    update_dict = {
        col: getattr(stmt.excluded, col)
        for col in processed_records[0].keys()
        if col not in ["id", "created_at", "user_id", "source"]
    }
    return stmt.on_conflict_do_update(
        index_elements=conflict_columns, set_=update_dict
    ).returning(literal_column("(xmax = 0)").label("is_insert"))


def bulk_upsert_records(
    records: list,
    model_class,
    unique_fields: list,
    user_id: int,
    source: str | None = None,
) -> dict:
    if not records:
        return {"created": 0, "updated": 0, "errors": 0}

    error_count = [0]
    result: dict = {"created": 0, "updated": 0, "errors": 0}

    try:
        with get_db_session_context() as db:
            processed_records = _process_upsert_records(
                records, model_class, user_id, source, error_count
            )
            result["errors"] = error_count[0]

            if not processed_records:
                return result

            stmt = _build_upsert_stmt(model_class, processed_records, unique_fields)
            rows = db.execute(stmt).fetchall()
            created = sum(1 for row in rows if row.is_insert)
            result["created"] = created
            result["updated"] = len(rows) - created

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
