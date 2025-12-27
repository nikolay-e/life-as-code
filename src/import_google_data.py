#!/usr/bin/env python3
import csv
import datetime
from pathlib import Path

from database import get_db_session_context
from enums import DataSource, DataType, SyncStatus
from google_schemas import GoogleDailyData
from logging_config import get_logger
from models import DataSync, HeartRate, Steps, User, Weight

logger = get_logger(__name__)

GOOGLE_DATA_PATH = Path(
    "/Users/nikolay/code/life-as-code/data/google/Takeout/Fit/Daily activity metrics"
)


def parse_csv_file(file_path: Path) -> list[dict]:
    rows = []
    try:
        with open(file_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
    except Exception as e:
        logger.error(f"Error reading {file_path}: {e}")
    return rows


def get_date_from_filename(filename: str) -> datetime.date | None:
    try:
        date_str = filename.replace(".csv", "")
        return datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return None


class ImportStats:
    def __init__(self) -> None:
        self.files_processed: int = 0
        self.steps_imported: int = 0
        self.heart_rate_imported: int = 0
        self.weight_imported: int = 0
        self.errors: list[str] = []

    def to_dict(self) -> dict[str, int | list[str]]:
        return {
            "files_processed": self.files_processed,
            "steps_imported": self.steps_imported,
            "heart_rate_imported": self.heart_rate_imported,
            "weight_imported": self.weight_imported,
            "errors": self.errors,
        }


def import_google_data_for_user(
    user_id: int,
    data_path: Path = GOOGLE_DATA_PATH,
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
    dry_run: bool = False,
) -> dict[str, int | list[str]]:
    stats = ImportStats()

    if not data_path.exists():
        logger.error(f"Google data path not found: {data_path}")
        stats.errors.append(f"Path not found: {data_path}")
        return stats.to_dict()

    csv_files = sorted(data_path.glob("????-??-??.csv"))
    logger.info(f"Found {len(csv_files)} daily CSV files")

    with get_db_session_context() as session:
        user = session.query(User).filter_by(id=user_id).first()
        if not user:
            logger.error(f"User {user_id} not found")
            stats.errors.append(f"User {user_id} not found")
            return stats.to_dict()

        for csv_file in csv_files:
            file_date = get_date_from_filename(csv_file.name)
            if not file_date:
                continue

            if start_date and file_date < start_date:
                continue
            if end_date and file_date > end_date:
                continue

            rows = parse_csv_file(csv_file)
            if not rows:
                continue

            try:
                daily_data = GoogleDailyData.from_csv_aggregation(file_date, rows)
                stats.files_processed += 1

                if dry_run:
                    logger.debug(f"[DRY RUN] Would import {file_date}: {daily_data}")
                    continue

                if daily_data.total_steps is not None:
                    existing_steps = (
                        session.query(Steps)
                        .filter_by(user_id=user_id, date=file_date)
                        .first()
                    )
                    if not existing_steps:
                        steps_record = Steps(
                            user_id=user_id,
                            date=file_date,
                            total_steps=daily_data.total_steps,
                            total_distance=daily_data.total_distance,
                            active_minutes=daily_data.move_minutes,
                        )
                        session.add(steps_record)
                        stats.steps_imported += 1

                if daily_data.avg_heart_rate is not None:
                    existing_hr = (
                        session.query(HeartRate)
                        .filter_by(user_id=user_id, date=file_date)
                        .first()
                    )
                    if not existing_hr:
                        hr_record = HeartRate(
                            user_id=user_id,
                            date=file_date,
                            avg_hr=daily_data.avg_heart_rate,
                            max_hr=daily_data.max_heart_rate,
                            resting_hr=daily_data.min_heart_rate,
                        )
                        session.add(hr_record)
                        stats.heart_rate_imported += 1

                if daily_data.avg_weight_kg is not None:
                    existing_weight = (
                        session.query(Weight)
                        .filter_by(user_id=user_id, date=file_date)
                        .first()
                    )
                    if not existing_weight:
                        weight_record = Weight(
                            user_id=user_id,
                            date=file_date,
                            weight_kg=daily_data.avg_weight_kg,
                        )
                        session.add(weight_record)
                        stats.weight_imported += 1

                if stats.files_processed % 100 == 0:
                    session.commit()
                    logger.info(f"Processed {stats.files_processed} files...")

            except Exception as e:
                logger.error(f"Error processing {csv_file}: {e}")
                stats.errors.append(f"{csv_file.name}: {e}")

        if not dry_run:
            session.commit()

            for data_type in [DataType.STEPS, DataType.HEART_RATE, DataType.WEIGHT]:
                sync_record = (
                    session.query(DataSync)
                    .filter_by(
                        user_id=user_id,
                        source=DataSource.GOOGLE.value,
                        data_type=data_type.value,
                    )
                    .first()
                )
                if sync_record:
                    sync_record.last_sync_date = datetime.date.today()
                    sync_record.last_sync_timestamp = datetime.datetime.utcnow()
                    sync_record.status = SyncStatus.SUCCESS.value
                else:
                    sync_record = DataSync(
                        user_id=user_id,
                        source=DataSource.GOOGLE.value,
                        data_type=data_type.value,
                        last_sync_date=datetime.date.today(),
                        last_sync_timestamp=datetime.datetime.utcnow(),
                        status=SyncStatus.SUCCESS.value,
                        records_synced=getattr(stats, f"{data_type.value}_imported", 0),
                    )
                    session.add(sync_record)
            session.commit()

    logger.info(f"Import complete: {stats.to_dict()}")
    return stats.to_dict()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Import Google Fit data")
    parser.add_argument(
        "--user-id", type=int, required=True, help="User ID to import data for"
    )
    parser.add_argument(
        "--data-path",
        type=str,
        default=str(GOOGLE_DATA_PATH),
        help="Path to Google Fit CSV files",
    )
    parser.add_argument("--start-date", type=str, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", type=str, help="End date (YYYY-MM-DD)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't actually import, just show what would be done",
    )
    args = parser.parse_args()

    start_date = None
    end_date = None

    if args.start_date:
        start_date = datetime.datetime.strptime(args.start_date, "%Y-%m-%d").date()
    if args.end_date:
        end_date = datetime.datetime.strptime(args.end_date, "%Y-%m-%d").date()

    data_path = Path(args.data_path)

    logger.info(f"Starting Google Fit import for user {args.user_id}")
    logger.info(f"Data path: {data_path}")
    logger.info(f"Date range: {start_date or 'beginning'} to {end_date or 'now'}")
    logger.info(f"Dry run: {args.dry_run}")

    stats = import_google_data_for_user(
        user_id=args.user_id,
        data_path=data_path,
        start_date=start_date,
        end_date=end_date,
        dry_run=args.dry_run,
    )

    print("\n=== Import Summary ===")
    print(f"Files processed: {stats['files_processed']}")
    print(f"Steps records imported: {stats['steps_imported']}")
    print(f"Heart rate records imported: {stats['heart_rate_imported']}")
    print(f"Weight records imported: {stats['weight_imported']}")
    if stats["errors"]:
        print(f"Errors: {len(stats['errors'])}")
        for err in stats["errors"][:10]:
            print(f"  - {err}")


if __name__ == "__main__":
    main()
