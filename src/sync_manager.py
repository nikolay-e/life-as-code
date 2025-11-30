"""
Generic sync manager for external data sources.
Provides common utilities for data extraction, parsing, and database operations.
"""

import datetime
import logging
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_db_session_context
from models import Base, DataSync

logger = logging.getLogger(__name__)


class SyncResult:
    """Container for sync operation results."""

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
        logger.error(f"Sync error for {self.source}/{self.data_type}: {error}")

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
    """
    Generic extraction and parsing decorator.

    Args:
        api_call_func: Function that makes the API call
        parser_class: Pydantic model for parsing API response
        model_class: SQLAlchemy model for database storage
        unique_fields: Fields that make a record unique
        user_id: User ID
        source: Data source name (e.g., "garmin", "heavy")
        data_type: Type of data (e.g., "sleep", "workouts")
        **api_kwargs: Additional arguments for the API call

    Returns:
        SyncResult: Results of the sync operation
    """
    sync_result = SyncResult(source, data_type, user_id)

    try:
        # Make API call
        logger.info(f"Starting {source} {data_type} sync for user {user_id}")
        api_response = api_call_func(**api_kwargs)

        if not api_response:
            sync_result.add_error("No data returned from API")
            sync_result.finish(False)
            return sync_result

        # Handle both list and single item responses
        if not isinstance(api_response, list):
            api_response = [api_response]

        with get_db_session_context() as db:
            for item in api_response:
                try:
                    # Parse with Pydantic model
                    if hasattr(parser_class, "from_api_response"):
                        parsed_data = parser_class.from_api_response(item)
                    elif hasattr(parser_class, "from_garmin_response"):
                        parsed_data = parser_class.from_garmin_response(item)
                    else:
                        parsed_data = parser_class(**item)

                    # Handle case where parser returns a list (like Heavy workouts)
                    if isinstance(parsed_data, list):
                        for data_item in parsed_data:
                            if data_item:
                                upsert_data(
                                    db,
                                    model_class,
                                    data_item,
                                    unique_fields,
                                    user_id,
                                    sync_result,
                                )
                                sync_result.records_processed += 1
                            else:
                                sync_result.records_skipped += 1
                    elif parsed_data:
                        upsert_data(
                            db,
                            model_class,
                            parsed_data,
                            unique_fields,
                            user_id,
                            sync_result,
                        )
                        sync_result.records_processed += 1
                    else:
                        sync_result.records_skipped += 1

                except Exception as e:
                    sync_result.add_error(f"Error parsing item: {str(e)}")
                    sync_result.records_skipped += 1
                    continue

            # Update sync tracking
            update_sync_status(db, user_id, source, data_type, sync_result)

        sync_result.finish(True)

    except Exception as e:
        sync_result.add_error(f"Fatal error in {source} {data_type} sync: {str(e)}")
        sync_result.finish(False)

    return sync_result


def update_sync_status(
    db: Session, user_id: int, source: str, data_type: str, sync_result: SyncResult
):
    """Update the DataSync table with sync results."""
    try:
        # Find existing sync record
        existing_sync = db.scalars(
            select(DataSync).where(
                DataSync.user_id == user_id,
                DataSync.source == source,
                DataSync.data_type == data_type,
            )
        ).first()

        status = "completed" if sync_result.success else "failed"
        error_message = (
            "; ".join(sync_result.errors[:3]) if sync_result.errors else None
        )

        if existing_sync:
            existing_sync.last_sync_timestamp = (
                sync_result.end_time or datetime.datetime.utcnow()
            )
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
                last_sync_timestamp=sync_result.end_time or datetime.datetime.utcnow(),
                records_synced=sync_result.records_created
                + sync_result.records_updated,
                status=status,
                error_message=error_message,
            )
            db.add(new_sync)

    except Exception as e:
        logger.error(f"Error updating sync status: {e}")


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
        logger.error(f"Error getting sync statistics: {e}")
        return {"error": str(e)}
