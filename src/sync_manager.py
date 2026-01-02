import datetime
import threading
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import bulk_upsert_records, get_db_session_context
from enums import DataSource, SyncStatus
from logging_config import get_logger
from models import Base, DataSync
from security import decrypt_data_for_user
from utils import get_user_credentials

logger = get_logger(__name__)


@dataclass
class SyncDateRange:
    start_date: datetime.date | None
    end_date: datetime.date
    sync_type: str


@dataclass
class ProviderCredentials:
    garmin_email: str | None = None
    garmin_password: str | None = None
    hevy_api_key: str | None = None
    whoop_access_token: str | None = None
    whoop_refresh_token: str | None = None


def get_sync_date_range(
    days: int = 90, full_sync: bool = False, max_history_days: int = 730
) -> SyncDateRange:
    end_date = datetime.date.today()
    if full_sync:
        start_date = end_date - datetime.timedelta(days=max_history_days)
    else:
        start_date = end_date - datetime.timedelta(days=days)
    sync_type = "full" if full_sync else f"{days}-day"
    return SyncDateRange(start_date=start_date, end_date=end_date, sync_type=sync_type)


def get_provider_credentials(
    user_id: int, provider: DataSource
) -> ProviderCredentials | dict[str, str]:
    try:
        creds = get_user_credentials(user_id)
        if not creds:
            return {"error": f"No credentials found for user {user_id}"}

        if provider == DataSource.GARMIN:
            if not creds.garmin_email:
                return {"error": "No Garmin credentials found for user"}
            return ProviderCredentials(
                garmin_email=creds.garmin_email,
                garmin_password=decrypt_data_for_user(
                    creds.encrypted_garmin_password, user_id
                ),
            )

        elif provider == DataSource.HEVY:
            if not creds.encrypted_hevy_api_key:
                return {"error": "No Hevy API key found for user"}
            return ProviderCredentials(
                hevy_api_key=decrypt_data_for_user(
                    creds.encrypted_hevy_api_key, user_id
                ),
            )

        elif provider == DataSource.WHOOP:
            if not creds.encrypted_whoop_access_token:
                return {"error": "No Whoop credentials found for user"}
            return ProviderCredentials(
                whoop_access_token=decrypt_data_for_user(
                    creds.encrypted_whoop_access_token, user_id
                ),
                whoop_refresh_token=decrypt_data_for_user(
                    creds.encrypted_whoop_refresh_token, user_id
                ),
            )

        return {"error": f"Unknown provider: {provider}"}

    except Exception as e:
        return {"error": f"Failed to get user credentials: {str(e)}"}


_sync_locks: dict[tuple[int, str], threading.Lock] = {}
_locks_lock = threading.Lock()


def _get_sync_lock(user_id: int, source: str) -> threading.Lock:
    key = (user_id, source)
    with _locks_lock:
        if key not in _sync_locks:
            _sync_locks[key] = threading.Lock()
        return _sync_locks[key]


def is_sync_in_progress(user_id: int, source: str) -> bool:
    lock = _get_sync_lock(user_id, source)
    acquired = lock.acquire(blocking=False)
    if acquired:
        lock.release()
        return False
    return True


class SyncResult:
    def __init__(self, source: str, data_type: str, user_id: int):
        self.source = source
        self.data_type = data_type
        self.user_id = user_id
        self.records_processed = 0
        self.records_created = 0
        self.records_updated = 0
        self.records_skipped = 0
        self.errors: list[str] = []
        self.start_time = datetime.datetime.utcnow()
        self.end_time: datetime.datetime | None = None
        self.success = False

    def add_error(self, error: str):
        """Add an error to the sync result."""
        self.errors.append(error)
        logger.error(
            "sync_error", source=self.source, data_type=self.data_type, error=error
        )

    def finish(self, success: bool = True):
        """Mark the sync as finished."""
        self.end_time = datetime.datetime.utcnow()
        self.success = success

        status = "completed" if success else "failed"
        logger.info(
            f"Sync {status} for {self.source}/{self.data_type}: "
            f"processed={self.records_processed}, created={self.records_created}, "
            f"updated={self.records_updated}, skipped={self.records_skipped}, "
            f"errors={len(self.errors)}"
        )

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of the sync results."""
        duration = None
        if self.end_time and self.start_time:
            duration = (self.end_time - self.start_time).total_seconds()

        return {
            "source": self.source,
            "data_type": self.data_type,
            "user_id": self.user_id,
            "success": self.success,
            "records_processed": self.records_processed,
            "records_created": self.records_created,
            "records_updated": self.records_updated,
            "records_skipped": self.records_skipped,
            "error_count": len(self.errors),
            "errors": self.errors[:5],  # First 5 errors only
            "duration_seconds": duration,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
        }


def upsert_data(
    db: Session,
    model_class: type[Base],
    data_instance: BaseModel | dict,
    unique_fields: list[str],
    user_id: int,
    sync_result: SyncResult,
) -> bool:
    """
    Generic upsert function for database models.

    Args:
        db: Database session
        model_class: SQLAlchemy model class
        data_instance: Pydantic model or dict with data
        unique_fields: List of field names that make the record unique
        user_id: User ID for the record
        sync_result: SyncResult object to track progress

    Returns:
        bool: True if record was created, False if updated
    """
    try:
        # Convert Pydantic model to dict if necessary
        if isinstance(data_instance, BaseModel):
            data_dict = data_instance.model_dump(exclude_none=True)
        else:
            data_dict = data_instance.copy()

        # Add user_id to the data
        data_dict["user_id"] = user_id

        # Build query to find existing record
        query = select(model_class).where(model_class.user_id == user_id)
        for field in unique_fields:
            if field in data_dict:
                query = query.where(getattr(model_class, field) == data_dict[field])

        existing = db.scalars(query).first()

        if existing:
            # Update existing record
            for key, value in data_dict.items():
                if hasattr(existing, key) and value is not None:
                    setattr(existing, key, value)
            sync_result.records_updated += 1
            return False
        else:
            # Create new record
            new_record = model_class(**data_dict)
            db.add(new_record)
            sync_result.records_created += 1
            return True

    except Exception as e:
        sync_result.add_error(f"Error upserting {model_class.__name__}: {str(e)}")
        sync_result.records_skipped += 1
        return False


def extract_and_parse(
    api_call_func,
    parser_class: type[BaseModel],
    model_class: type[Base],
    unique_fields: list[str],
    user_id: int,
    source: str,
    data_type: str,
    **api_kwargs,
) -> SyncResult:
    sync_result = SyncResult(source, data_type, user_id)
    lock = _get_sync_lock(user_id, source)

    if not lock.acquire(blocking=False):
        sync_result.add_error(f"Sync already in progress for {source}")
        sync_result.finish(False)
        return sync_result

    try:
        with get_db_session_context() as db:
            _set_sync_in_progress(db, user_id, source, data_type)

        logger.info("sync_started", source=source, data_type=data_type, user_id=user_id)
        api_response = api_call_func(**api_kwargs)

        if api_response is None:
            sync_result.add_error("No data returned from API")
            sync_result.finish(False)
            with get_db_session_context() as db:
                update_sync_status(db, user_id, source, data_type, sync_result)
            return sync_result

        if not isinstance(api_response, list):
            api_response = [api_response]

        all_records: list = []
        for item in api_response:
            try:
                if hasattr(parser_class, "from_api_response"):
                    parsed_data = parser_class.from_api_response(item)
                elif hasattr(parser_class, "from_garmin_response"):
                    parsed_data = parser_class.from_garmin_response(item)
                else:
                    parsed_data = parser_class(**item)

                if isinstance(parsed_data, list):
                    for data_item in parsed_data:
                        if data_item:
                            all_records.append(data_item)
                            sync_result.records_processed += 1
                        else:
                            sync_result.records_skipped += 1
                elif parsed_data:
                    all_records.append(parsed_data)
                    sync_result.records_processed += 1
                else:
                    sync_result.records_skipped += 1

            except Exception as e:
                sync_result.add_error(f"Error parsing item: {str(e)}")
                sync_result.records_skipped += 1
                continue

        if all_records:
            result = bulk_upsert_records(
                all_records, model_class, unique_fields, user_id
            )
            if "error" in result:
                sync_result.add_error(result["error"])
            else:
                sync_result.records_created = result.get("created", 0)
                sync_result.records_updated = result.get("updated", 0)

        with get_db_session_context() as db:
            update_sync_status(db, user_id, source, data_type, sync_result)

        sync_result.finish(True)

    except Exception as e:
        sync_result.add_error(f"Fatal error in {source} {data_type} sync: {str(e)}")
        sync_result.finish(False)
        try:
            with get_db_session_context() as db:
                update_sync_status(db, user_id, source, data_type, sync_result)
        except Exception:
            pass

    finally:
        lock.release()

    return sync_result


def _set_sync_in_progress(db: Session, user_id: int, source: str, data_type: str):
    try:
        existing_sync = db.scalars(
            select(DataSync).where(
                DataSync.user_id == user_id,
                DataSync.source == source,
                DataSync.data_type == data_type,
            )
        ).first()

        if existing_sync:
            existing_sync.status = SyncStatus.IN_PROGRESS
            existing_sync.error_message = None
        else:
            new_sync = DataSync(
                user_id=user_id,
                source=source,
                data_type=data_type,
                status=SyncStatus.IN_PROGRESS,
            )
            db.add(new_sync)

    except Exception as e:
        logger.error("sync_in_progress_error", error=str(e))


def update_sync_status(
    db: Session, user_id: int, source: str, data_type: str, sync_result: SyncResult
):
    try:
        existing_sync = db.scalars(
            select(DataSync).where(
                DataSync.user_id == user_id,
                DataSync.source == source,
                DataSync.data_type == data_type,
            )
        ).first()

        status = SyncStatus.SUCCESS if sync_result.success else SyncStatus.ERROR
        error_message = (
            "; ".join(sync_result.errors[:3]) if sync_result.errors else None
        )

        sync_timestamp = sync_result.end_time or datetime.datetime.utcnow()
        sync_date = sync_timestamp.date()

        if existing_sync:
            existing_sync.last_sync_timestamp = sync_timestamp
            existing_sync.last_sync_date = sync_date
            existing_sync.records_synced = (
                sync_result.records_created + sync_result.records_updated
            )
            existing_sync.status = status
            existing_sync.error_message = error_message
        else:
            new_sync = DataSync(
                user_id=user_id,
                source=source,
                data_type=data_type,
                last_sync_timestamp=sync_timestamp,
                last_sync_date=sync_date,
                records_synced=sync_result.records_created
                + sync_result.records_updated,
                status=status,
                error_message=error_message,
            )
            db.add(new_sync)

    except Exception as e:
        logger.error("sync_status_update_error", error=str(e))


def batch_sync_data(
    sync_configs: list[dict[str, Any]], user_id: int, api_client: Any
) -> list[SyncResult]:
    """
    Batch sync multiple data types using a common API client.

    Args:
        sync_configs: List of sync configuration dicts, each containing:
            - data_type: Type of data to sync
            - api_method: Method name on the API client
            - parser_class: Pydantic model for parsing
            - model_class: SQLAlchemy model for storage
            - unique_fields: Fields that make records unique
            - api_args: Additional arguments for API call
        user_id: User ID
        api_client: Initialized API client

    Returns:
        List[SyncResult]: Results for each sync operation
    """
    results = []

    for config in sync_configs:
        try:
            # Get the API method
            api_method = getattr(api_client, config["api_method"])

            # Perform the sync
            result = extract_and_parse(
                api_call_func=api_method,
                parser_class=config["parser_class"],
                model_class=config["model_class"],
                unique_fields=config["unique_fields"],
                user_id=user_id,
                source=config.get("source", "unknown"),
                data_type=config["data_type"],
                **config.get("api_args", {}),
            )

            results.append(result)

        except Exception as e:
            # Create failed result
            failed_result = SyncResult(
                config.get("source", "unknown"), config["data_type"], user_id
            )
            failed_result.add_error(f"Failed to sync {config['data_type']}: {str(e)}")
            failed_result.finish(False)
            results.append(failed_result)

    return results


def get_sync_statistics(user_id: int, source: str | None = None) -> dict[str, Any]:
    """Get sync statistics for a user."""
    try:
        with get_db_session_context() as db:
            query = select(DataSync).where(DataSync.user_id == user_id)

            if source:
                query = query.where(DataSync.source == source)

            syncs = db.scalars(query).all()

            stats: dict[str, Any] = {
                "total_syncs": len(syncs),
                "successful_syncs": len([s for s in syncs if s.status == "completed"]),
                "failed_syncs": len([s for s in syncs if s.status == "failed"]),
                "total_records_synced": sum(s.records_synced or 0 for s in syncs),
                "last_sync": None,
                "sync_details": [],
            }

            if syncs:
                # Get most recent sync
                most_recent = max(
                    syncs, key=lambda s: s.last_sync_timestamp or datetime.datetime.min
                )
                stats["last_sync"] = (
                    most_recent.last_sync_timestamp.isoformat()
                    if most_recent.last_sync_timestamp
                    else None
                )

                # Sync details by data type
                for sync in syncs:
                    stats["sync_details"].append(
                        {
                            "source": sync.source,
                            "data_type": sync.data_type,
                            "status": sync.status,
                            "records_synced": sync.records_synced,
                            "last_sync": (
                                sync.last_sync_timestamp.isoformat()
                                if sync.last_sync_timestamp
                                else None
                            ),
                            "error": sync.error_message,
                        }
                    )

            return stats

    except Exception as e:
        logger.error("sync_statistics_error", error=str(e))
        return {"error": str(e)}
