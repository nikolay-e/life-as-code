#!/usr/bin/env python3
import datetime
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from database import get_db_session_context
from enums import DataSource, DataType, SyncStatus
from logging_config import get_logger
from models import DataSync, Energy, HeartRate, Sleep, User, Weight

logger = get_logger(__name__)

GOOGLE_DATA_BASE = Path("/Users/nikolay/code/life-as-code/data/google")

SLEEP_SEGMENT_AWAKE = 1
SLEEP_SEGMENT_LIGHT = 4
SLEEP_SEGMENT_DEEP = 5
SLEEP_SEGMENT_REM = 6


class ImportStats:
    def __init__(self) -> None:
        self.files_processed: int = 0
        self.rhr_imported: int = 0
        self.sleep_imported: int = 0
        self.spo2_imported: int = 0
        self.respiratory_rate_imported: int = 0
        self.body_fat_imported: int = 0
        self.calories_imported: int = 0
        self.errors: list[str] = []

    def to_dict(self) -> dict[str, int | list[str]]:
        return {
            "files_processed": self.files_processed,
            "rhr_imported": self.rhr_imported,
            "sleep_imported": self.sleep_imported,
            "spo2_imported": self.spo2_imported,
            "respiratory_rate_imported": self.respiratory_rate_imported,
            "body_fat_imported": self.body_fat_imported,
            "calories_imported": self.calories_imported,
            "errors": self.errors,
        }


def nanos_to_date(nanos: int) -> datetime.date:
    timestamp_seconds = nanos / 1_000_000_000
    return datetime.datetime.fromtimestamp(timestamp_seconds).date()


def nanos_to_minutes(start_nanos: int, end_nanos: int) -> float:
    duration_nanos = end_nanos - start_nanos
    return duration_nanos / 1_000_000_000 / 60


def find_all_data_dirs(base_path: Path) -> list[Path]:
    all_data_dirs = []
    for takeout_dir in base_path.glob("Takeout*"):
        fit_all_data = takeout_dir / "Takeout" / "Fit" / "All Data"
        if fit_all_data.exists():
            all_data_dirs.append(fit_all_data)
    if not all_data_dirs:
        fit_all_data = base_path / "Takeout" / "Fit" / "All Data"
        if fit_all_data.exists():
            all_data_dirs.append(fit_all_data)
    return all_data_dirs


def load_json_file(file_path: Path) -> dict[str, Any] | None:
    try:
        with open(file_path, encoding="utf-8") as f:
            result: dict[str, Any] = json.load(f)
            return result
    except Exception as e:
        logger.error(f"Error reading {file_path}: {e}")
        return None


def extract_rhr_data(all_data_dirs: list[Path]) -> dict[datetime.date, int]:
    daily_rhr: dict[datetime.date, list[float]] = defaultdict(list)

    for data_dir in all_data_dirs:
        for json_file in data_dir.glob("*heart_rate*.json"):
            data = load_json_file(json_file)
            if not data:
                continue

            data_source = data.get("Data Source", "")
            if "resting_heart_rate" not in data_source:
                continue

            for point in data.get("Data Points", []):
                fit_values = point.get("fitValue", [])
                if not fit_values:
                    continue

                value_obj = fit_values[0].get("value", {})
                hr_value = value_obj.get("fpVal")
                if hr_value is None:
                    continue

                start_nanos = point.get("startTimeNanos")
                if not start_nanos:
                    continue

                date = nanos_to_date(start_nanos)
                daily_rhr[date].append(hr_value)

    result: dict[datetime.date, int] = {}
    for date, values in daily_rhr.items():
        result[date] = int(min(values))

    logger.info(f"Extracted RHR for {len(result)} days")
    return result


def extract_sleep_data(
    all_data_dirs: list[Path],
) -> dict[datetime.date, dict[str, float]]:
    sleep_segments: list[tuple[datetime.date, int, float]] = []

    for data_dir in all_data_dirs:
        for json_file in data_dir.glob("*sleep.segment*.json"):
            data = load_json_file(json_file)
            if not data:
                continue

            for point in data.get("Data Points", []):
                fit_values = point.get("fitValue", [])
                if not fit_values:
                    continue

                value_obj = fit_values[0].get("value", {})
                segment_type = value_obj.get("intVal")
                if segment_type is None:
                    continue

                start_nanos = point.get("startTimeNanos")
                end_nanos = point.get("endTimeNanos")
                if not start_nanos or not end_nanos:
                    continue

                date = nanos_to_date(end_nanos)
                duration_minutes = nanos_to_minutes(start_nanos, end_nanos)
                sleep_segments.append((date, segment_type, duration_minutes))

    daily_sleep: dict[datetime.date, dict[str, float]] = defaultdict(
        lambda: {
            "deep_minutes": 0.0,
            "light_minutes": 0.0,
            "rem_minutes": 0.0,
            "awake_minutes": 0.0,
            "total_sleep_minutes": 0.0,
        }
    )

    for date, segment_type, duration in sleep_segments:
        if segment_type == SLEEP_SEGMENT_DEEP:
            daily_sleep[date]["deep_minutes"] += duration
            daily_sleep[date]["total_sleep_minutes"] += duration
        elif segment_type == SLEEP_SEGMENT_LIGHT:
            daily_sleep[date]["light_minutes"] += duration
            daily_sleep[date]["total_sleep_minutes"] += duration
        elif segment_type == SLEEP_SEGMENT_REM:
            daily_sleep[date]["rem_minutes"] += duration
            daily_sleep[date]["total_sleep_minutes"] += duration
        elif segment_type == SLEEP_SEGMENT_AWAKE:
            daily_sleep[date]["awake_minutes"] += duration

    logger.info(f"Extracted sleep data for {len(daily_sleep)} days")
    return dict(daily_sleep)


def extract_spo2_data(
    all_data_dirs: list[Path],
) -> dict[datetime.date, dict[str, float]]:
    daily_spo2: dict[datetime.date, list[float]] = defaultdict(list)

    for data_dir in all_data_dirs:
        for json_file in data_dir.glob("*oxygen_saturation*.json"):
            data = load_json_file(json_file)
            if not data:
                continue

            for point in data.get("Data Points", []):
                fit_values = point.get("fitValue", [])
                if not fit_values:
                    continue

                value_obj = fit_values[0].get("value", {})
                spo2_value = value_obj.get("fpVal")
                if spo2_value is None or spo2_value < 50 or spo2_value > 100:
                    continue

                start_nanos = point.get("startTimeNanos")
                if not start_nanos:
                    continue

                date = nanos_to_date(start_nanos)
                daily_spo2[date].append(spo2_value)

    result: dict[datetime.date, dict[str, float]] = {}
    for date, values in daily_spo2.items():
        result[date] = {
            "spo2_avg": sum(values) / len(values),
            "spo2_min": min(values),
        }

    logger.info(f"Extracted SpO2 for {len(result)} days")
    return result


def extract_respiratory_rate_data(
    all_data_dirs: list[Path],
) -> dict[datetime.date, float]:
    daily_rr: dict[datetime.date, list[float]] = defaultdict(list)

    for data_dir in all_data_dirs:
        for json_file in data_dir.glob("*respiratory_rate*.json"):
            data = load_json_file(json_file)
            if not data:
                continue

            for point in data.get("Data Points", []):
                fit_values = point.get("fitValue", [])
                if not fit_values:
                    continue

                value_obj = fit_values[0].get("value", {})
                rr_value = value_obj.get("fpVal")
                if rr_value is None or rr_value < 5 or rr_value > 50:
                    continue

                start_nanos = point.get("startTimeNanos")
                if not start_nanos:
                    continue

                date = nanos_to_date(start_nanos)
                daily_rr[date].append(rr_value)

    result: dict[datetime.date, float] = {}
    for date, values in daily_rr.items():
        result[date] = sum(values) / len(values)

    logger.info(f"Extracted respiratory rate for {len(result)} days")
    return result


def extract_body_fat_data(all_data_dirs: list[Path]) -> dict[datetime.date, float]:
    daily_bf: dict[datetime.date, list[float]] = defaultdict(list)

    for data_dir in all_data_dirs:
        for json_file in data_dir.glob("*body.fat.percentage*.json"):
            data = load_json_file(json_file)
            if not data:
                continue

            for point in data.get("Data Points", []):
                fit_values = point.get("fitValue", [])
                if not fit_values:
                    continue

                value_obj = fit_values[0].get("value", {})
                bf_value = value_obj.get("fpVal")
                if bf_value is None or bf_value < 1 or bf_value > 60:
                    continue

                start_nanos = point.get("startTimeNanos")
                if not start_nanos:
                    continue

                date = nanos_to_date(start_nanos)
                daily_bf[date].append(bf_value)

    result: dict[datetime.date, float] = {}
    for date, values in daily_bf.items():
        result[date] = sum(values) / len(values)

    logger.info(f"Extracted body fat for {len(result)} days")
    return result


def extract_calories_data(
    all_data_dirs: list[Path],
    min_total_calories: float = 2000.0,
) -> dict[datetime.date, dict[str, float]]:
    daily_active: dict[datetime.date, float] = defaultdict(float)
    daily_bmr: dict[datetime.date, float] = defaultdict(float)

    for data_dir in all_data_dirs:
        for json_file in data_dir.glob("*calories.expended*.json"):
            data = load_json_file(json_file)
            if not data:
                continue

            for point in data.get("Data Points", []):
                fit_values = point.get("fitValue", [])
                if not fit_values:
                    continue

                value_obj = fit_values[0].get("value", {})
                cal_value = value_obj.get("fpVal")
                if cal_value is None or cal_value < 0 or cal_value > 50000:
                    continue

                end_nanos = point.get("endTimeNanos")
                if not end_nanos:
                    continue

                date = nanos_to_date(end_nanos)
                origin = point.get("originDataSourceId", "")

                if "from_activities" in origin:
                    daily_active[date] += cal_value
                elif "from_bmr" in origin:
                    daily_bmr[date] += cal_value

    result: dict[datetime.date, dict[str, float]] = {}
    all_dates = set(daily_active.keys()) | set(daily_bmr.keys())
    skipped = 0
    for date in all_dates:
        active = daily_active.get(date, 0.0)
        basal = daily_bmr.get(date, 0.0)
        total = active + basal
        if total >= min_total_calories:
            result[date] = {
                "active_energy": active,
                "basal_energy": basal,
            }
        else:
            skipped += 1

    logger.info(
        f"Extracted calories for {len(result)} days "
        f"(skipped {skipped} incomplete days with total < {min_total_calories} kcal)"
    )
    return result


def import_google_fit_json(
    user_id: int,
    base_path: Path = GOOGLE_DATA_BASE,
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
    dry_run: bool = False,
) -> dict[str, int | list[str]]:
    stats = ImportStats()

    all_data_dirs = find_all_data_dirs(base_path)
    if not all_data_dirs:
        logger.error(f"No Google Fit All Data directories found in {base_path}")
        stats.errors.append(f"No All Data dirs found in {base_path}")
        return stats.to_dict()

    logger.info(f"Found {len(all_data_dirs)} All Data directories")
    for d in all_data_dirs:
        logger.info(f"  - {d}")

    rhr_data = extract_rhr_data(all_data_dirs)
    sleep_data = extract_sleep_data(all_data_dirs)
    spo2_data = extract_spo2_data(all_data_dirs)
    rr_data = extract_respiratory_rate_data(all_data_dirs)
    bf_data = extract_body_fat_data(all_data_dirs)
    calories_data = extract_calories_data(all_data_dirs)

    stats.files_processed = (
        len(rhr_data) + len(sleep_data) + len(bf_data) + len(calories_data)
    )

    with get_db_session_context() as session:
        user = session.query(User).filter_by(id=user_id).first()
        if not user:
            logger.error(f"User {user_id} not found")
            stats.errors.append(f"User {user_id} not found")
            return stats.to_dict()

        for date, rhr_value in rhr_data.items():
            if start_date and date < start_date:
                continue
            if end_date and date > end_date:
                continue

            if dry_run:
                logger.debug(f"[DRY RUN] Would update RHR for {date}: {rhr_value}")
                continue

            existing_hr = (
                session.query(HeartRate).filter_by(user_id=user_id, date=date).first()
            )
            if existing_hr:
                if existing_hr.resting_hr is None:
                    existing_hr.resting_hr = rhr_value
                    stats.rhr_imported += 1
            else:
                hr_record = HeartRate(
                    user_id=user_id,
                    date=date,
                    resting_hr=rhr_value,
                )
                session.add(hr_record)
                stats.rhr_imported += 1

        for date, sleep_values in sleep_data.items():
            if start_date and date < start_date:
                continue
            if end_date and date > end_date:
                continue

            if dry_run:
                logger.debug(f"[DRY RUN] Would import sleep for {date}: {sleep_values}")
                continue

            spo2 = spo2_data.get(date, {})
            rr = rr_data.get(date)

            existing_sleep = (
                session.query(Sleep).filter_by(user_id=user_id, date=date).first()
            )
            if existing_sleep:
                if existing_sleep.deep_minutes is None:
                    existing_sleep.deep_minutes = sleep_values["deep_minutes"]
                if existing_sleep.light_minutes is None:
                    existing_sleep.light_minutes = sleep_values["light_minutes"]
                if existing_sleep.rem_minutes is None:
                    existing_sleep.rem_minutes = sleep_values["rem_minutes"]
                if existing_sleep.awake_minutes is None:
                    existing_sleep.awake_minutes = sleep_values["awake_minutes"]
                if existing_sleep.total_sleep_minutes is None:
                    existing_sleep.total_sleep_minutes = sleep_values[
                        "total_sleep_minutes"
                    ]
                if existing_sleep.spo2_avg is None and spo2.get("spo2_avg"):
                    existing_sleep.spo2_avg = spo2["spo2_avg"]
                if existing_sleep.spo2_min is None and spo2.get("spo2_min"):
                    existing_sleep.spo2_min = spo2["spo2_min"]
                if existing_sleep.respiratory_rate is None and rr:
                    existing_sleep.respiratory_rate = rr
                stats.sleep_imported += 1
            else:
                sleep_record = Sleep(
                    user_id=user_id,
                    date=date,
                    deep_minutes=sleep_values["deep_minutes"],
                    light_minutes=sleep_values["light_minutes"],
                    rem_minutes=sleep_values["rem_minutes"],
                    awake_minutes=sleep_values["awake_minutes"],
                    total_sleep_minutes=sleep_values["total_sleep_minutes"],
                    spo2_avg=spo2.get("spo2_avg"),
                    spo2_min=spo2.get("spo2_min"),
                    respiratory_rate=rr,
                )
                session.add(sleep_record)
                stats.sleep_imported += 1

            if spo2:
                stats.spo2_imported += 1
            if rr:
                stats.respiratory_rate_imported += 1

        for date, bf_value in bf_data.items():
            if start_date and date < start_date:
                continue
            if end_date and date > end_date:
                continue

            if dry_run:
                logger.debug(f"[DRY RUN] Would update body fat for {date}: {bf_value}%")
                continue

            existing_weight = (
                session.query(Weight).filter_by(user_id=user_id, date=date).first()
            )
            if existing_weight:
                if existing_weight.body_fat_pct is None:
                    existing_weight.body_fat_pct = bf_value
                    stats.body_fat_imported += 1
            else:
                weight_record = Weight(
                    user_id=user_id,
                    date=date,
                    body_fat_pct=bf_value,
                )
                session.add(weight_record)
                stats.body_fat_imported += 1

        for date, cal_values in calories_data.items():
            if start_date and date < start_date:
                continue
            if end_date and date > end_date:
                continue

            if dry_run:
                total = cal_values["active_energy"] + cal_values["basal_energy"]
                logger.debug(
                    f"[DRY RUN] Would import calories for {date}: "
                    f"active={cal_values['active_energy']:.0f}, "
                    f"basal={cal_values['basal_energy']:.0f}, "
                    f"total={total:.0f}"
                )
                continue

            existing_energy = (
                session.query(Energy).filter_by(user_id=user_id, date=date).first()
            )
            if existing_energy:
                if (
                    existing_energy.active_energy is None
                    or existing_energy.active_energy == 0
                ):
                    existing_energy.active_energy = cal_values["active_energy"]
                if (
                    existing_energy.basal_energy is None
                    or existing_energy.basal_energy == 0
                ):
                    existing_energy.basal_energy = cal_values["basal_energy"]
                stats.calories_imported += 1
            else:
                energy_record = Energy(
                    user_id=user_id,
                    date=date,
                    active_energy=cal_values["active_energy"],
                    basal_energy=cal_values["basal_energy"],
                )
                session.add(energy_record)
                stats.calories_imported += 1

        if not dry_run:
            session.commit()

            for data_type in [
                DataType.SLEEP,
                DataType.HEART_RATE,
                DataType.WEIGHT,
                DataType.ENERGY,
            ]:
                sync_record = (
                    session.query(DataSync)
                    .filter_by(
                        user_id=user_id,
                        source=DataSource.GOOGLE.value,
                        data_type=data_type.value,
                    )
                    .first()
                )
                records_count = {
                    DataType.SLEEP: stats.sleep_imported,
                    DataType.HEART_RATE: stats.rhr_imported,
                    DataType.WEIGHT: stats.body_fat_imported,
                    DataType.ENERGY: stats.calories_imported,
                }.get(data_type, 0)

                if sync_record:
                    sync_record.last_sync_date = datetime.date.today()
                    sync_record.last_sync_timestamp = datetime.datetime.utcnow()
                    sync_record.status = SyncStatus.SUCCESS.value
                    sync_record.records_synced = (
                        sync_record.records_synced or 0
                    ) + records_count
                else:
                    sync_record = DataSync(
                        user_id=user_id,
                        source=DataSource.GOOGLE.value,
                        data_type=data_type.value,
                        last_sync_date=datetime.date.today(),
                        last_sync_timestamp=datetime.datetime.utcnow(),
                        status=SyncStatus.SUCCESS.value,
                        records_synced=records_count,
                    )
                    session.add(sync_record)
            session.commit()

    logger.info(f"Import complete: {stats.to_dict()}")
    return stats.to_dict()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Import Google Fit JSON data")
    parser.add_argument(
        "--user-id", type=int, required=True, help="User ID to import data for"
    )
    parser.add_argument(
        "--data-path",
        type=str,
        default=str(GOOGLE_DATA_BASE),
        help="Base path to Google Fit data (contains Takeout* directories)",
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

    base_path = Path(args.data_path)

    logger.info(f"Starting Google Fit JSON import for user {args.user_id}")
    logger.info(f"Base path: {base_path}")
    logger.info(f"Date range: {start_date or 'beginning'} to {end_date or 'now'}")
    logger.info(f"Dry run: {args.dry_run}")

    stats = import_google_fit_json(
        user_id=args.user_id,
        base_path=base_path,
        start_date=start_date,
        end_date=end_date,
        dry_run=args.dry_run,
    )

    print("\n=== Import Summary ===")
    print(f"Files processed: {stats['files_processed']}")
    print(f"RHR records imported: {stats['rhr_imported']}")
    print(f"Sleep records imported: {stats['sleep_imported']}")
    print(f"SpO2 records imported: {stats['spo2_imported']}")
    print(f"Respiratory rate records imported: {stats['respiratory_rate_imported']}")
    print(f"Body fat records imported: {stats['body_fat_imported']}")
    print(f"Calories records imported: {stats['calories_imported']}")
    if stats["errors"]:
        print(f"Errors: {len(stats['errors'])}")
        for err in stats["errors"][:10]:
            print(f"  - {err}")


if __name__ == "__main__":
    main()
