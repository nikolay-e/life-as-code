#!/usr/bin/env python3
import datetime
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any

import defusedxml.ElementTree as ET

from database import get_db_session_context
from enums import DataSource, DataType, SyncStatus
from logging_config import get_logger
from models import HRV, DataSync, Energy, HeartRate, Sleep, Steps, User, Weight

logger = get_logger(__name__)

SLEEP_VALUE_DEEP = "HKCategoryValueSleepAnalysisAsleepDeep"
SLEEP_VALUE_CORE = "HKCategoryValueSleepAnalysisAsleepCore"
SLEEP_VALUE_REM = "HKCategoryValueSleepAnalysisAsleepREM"
SLEEP_VALUE_AWAKE = "HKCategoryValueSleepAnalysisAwake"
SLEEP_VALUE_UNSPECIFIED = "HKCategoryValueSleepAnalysisAsleepUnspecified"
SLEEP_VALUE_IN_BED = "HKCategoryValueSleepAnalysisInBed"


class ImportStats:
    def __init__(self) -> None:
        self.records_processed: int = 0
        self.weight_imported: int = 0
        self.steps_imported: int = 0
        self.hrv_imported: int = 0
        self.rhr_imported: int = 0
        self.sleep_imported: int = 0
        self.calories_imported: int = 0
        self.errors: list[str] = []

    def to_dict(self) -> dict[str, int | list[str]]:
        return {
            "records_processed": self.records_processed,
            "weight_imported": self.weight_imported,
            "steps_imported": self.steps_imported,
            "hrv_imported": self.hrv_imported,
            "rhr_imported": self.rhr_imported,
            "sleep_imported": self.sleep_imported,
            "calories_imported": self.calories_imported,
            "errors": self.errors,
        }


def parse_apple_date(date_str: str) -> datetime.date | None:
    try:
        dt = datetime.datetime.strptime(date_str[:19], "%Y-%m-%d %H:%M:%S")
        return dt.date()
    except (ValueError, TypeError):
        return None


def parse_apple_datetime(date_str: str) -> datetime.datetime | None:
    try:
        return datetime.datetime.strptime(date_str[:19], "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return None


def calculate_duration_minutes(start_str: str, end_str: str) -> float:
    start = parse_apple_datetime(start_str)
    end = parse_apple_datetime(end_str)
    if start and end:
        delta = end - start
        return delta.total_seconds() / 60
    return 0.0


def extract_data_from_xml(xml_path: Path) -> dict[str, Any]:
    logger.info(f"Parsing Apple Health XML: {xml_path}")

    daily_weight: dict[datetime.date, list[float]] = defaultdict(list)
    daily_steps: dict[datetime.date, int] = defaultdict(int)
    daily_distance: dict[datetime.date, float] = defaultdict(float)
    daily_floors: dict[datetime.date, int] = defaultdict(int)
    daily_hrv: dict[datetime.date, list[float]] = defaultdict(list)
    daily_rhr: dict[datetime.date, list[float]] = defaultdict(list)
    daily_active_cal: dict[datetime.date, float] = defaultdict(float)
    daily_basal_cal: dict[datetime.date, float] = defaultdict(float)
    sleep_segments: list[tuple[datetime.date, str, float]] = []

    record_count = 0

    for _event, elem in ET.iterparse(xml_path, events=["end"]):
        if elem.tag == "Record":
            record_type = elem.get("type", "")
            value_str = elem.get("value", "")
            start_date = elem.get("startDate", "")
            end_date = elem.get("endDate", "")

            if record_type == "HKQuantityTypeIdentifierBodyMass":
                date = parse_apple_date(start_date)
                if date and value_str:
                    try:
                        weight = float(value_str)
                        unit = elem.get("unit", "kg")
                        if unit == "lb":
                            weight = weight * 0.453592
                        if 20 < weight < 300:
                            daily_weight[date].append(weight)
                    except ValueError:
                        pass

            elif record_type == "HKQuantityTypeIdentifierStepCount":
                date = parse_apple_date(end_date)
                if date and value_str:
                    try:
                        steps = int(float(value_str))
                        if steps > 0:
                            daily_steps[date] += steps
                    except ValueError:
                        pass

            elif record_type == "HKQuantityTypeIdentifierDistanceWalkingRunning":
                date = parse_apple_date(end_date)
                if date and value_str:
                    try:
                        distance = float(value_str)
                        unit = elem.get("unit", "km")
                        if unit == "mi":
                            distance = distance * 1.60934
                        elif unit == "m":
                            distance = distance / 1000
                        daily_distance[date] += distance
                    except ValueError:
                        pass

            elif record_type == "HKQuantityTypeIdentifierFlightsClimbed":
                date = parse_apple_date(end_date)
                if date and value_str:
                    try:
                        floors = int(float(value_str))
                        if floors > 0:
                            daily_floors[date] += floors
                    except ValueError:
                        pass

            elif record_type == "HKQuantityTypeIdentifierHeartRateVariabilitySDNN":
                date = parse_apple_date(start_date)
                if date and value_str:
                    try:
                        hrv = float(value_str)
                        if 0 < hrv < 500:
                            daily_hrv[date].append(hrv)
                    except ValueError:
                        pass

            elif record_type == "HKQuantityTypeIdentifierRestingHeartRate":
                date = parse_apple_date(start_date)
                if date and value_str:
                    try:
                        rhr = int(float(value_str))
                        if 20 <= rhr <= 200:
                            daily_rhr[date].append(rhr)
                    except ValueError:
                        pass

            elif record_type == "HKQuantityTypeIdentifierActiveEnergyBurned":
                date = parse_apple_date(end_date)
                if date and value_str:
                    try:
                        cal = float(value_str)
                        unit = elem.get("unit", "kcal")
                        if unit == "kJ":
                            cal = cal / 4.184
                        if 0 < cal < 50000:
                            daily_active_cal[date] += cal
                    except ValueError:
                        pass

            elif record_type == "HKQuantityTypeIdentifierBasalEnergyBurned":
                date = parse_apple_date(end_date)
                if date and value_str:
                    try:
                        cal = float(value_str)
                        unit = elem.get("unit", "kcal")
                        if unit == "kJ":
                            cal = cal / 4.184
                        if 0 < cal < 50000:
                            daily_basal_cal[date] += cal
                    except ValueError:
                        pass

            elif record_type == "HKCategoryTypeIdentifierSleepAnalysis":
                date = parse_apple_date(end_date)
                if date and value_str and value_str != SLEEP_VALUE_IN_BED:
                    duration = calculate_duration_minutes(start_date, end_date)
                    if duration > 0:
                        sleep_segments.append((date, value_str, duration))

            record_count += 1
            if record_count % 500000 == 0:
                logger.info(f"Processed {record_count:,} records...")

            elem.clear()

    logger.info(f"Finished parsing. Total records: {record_count:,}")

    weight_result: dict[datetime.date, float] = {}
    for date, values in daily_weight.items():
        weight_result[date] = sum(values) / len(values)

    hrv_result: dict[datetime.date, float] = {}
    for date, values in daily_hrv.items():
        hrv_result[date] = sum(values) / len(values)

    rhr_result: dict[datetime.date, int] = {}
    for date, values in daily_rhr.items():
        rhr_result[date] = int(min(values))

    steps_result: dict[datetime.date, dict[str, Any]] = {}
    all_step_dates = (
        set(daily_steps.keys()) | set(daily_distance.keys()) | set(daily_floors.keys())
    )
    for date in all_step_dates:
        steps_result[date] = {
            "total_steps": daily_steps.get(date, 0),
            "total_distance": daily_distance.get(date, 0.0),
            "floors_climbed": daily_floors.get(date, 0),
        }

    calories_result: dict[datetime.date, dict[str, float]] = {}
    min_total_calories = 1500.0
    all_cal_dates = set(daily_active_cal.keys()) | set(daily_basal_cal.keys())
    for date in all_cal_dates:
        active = daily_active_cal.get(date, 0.0)
        basal = daily_basal_cal.get(date, 0.0)
        total = active + basal
        if total >= min_total_calories:
            calories_result[date] = {
                "active_energy": active,
                "basal_energy": basal,
            }

    daily_sleep: dict[datetime.date, dict[str, float]] = defaultdict(
        lambda: {
            "deep_minutes": 0.0,
            "light_minutes": 0.0,
            "rem_minutes": 0.0,
            "awake_minutes": 0.0,
            "total_sleep_minutes": 0.0,
        }
    )

    for date, sleep_type, duration in sleep_segments:
        if sleep_type == SLEEP_VALUE_DEEP:
            daily_sleep[date]["deep_minutes"] += duration
            daily_sleep[date]["total_sleep_minutes"] += duration
        elif sleep_type in (SLEEP_VALUE_CORE, SLEEP_VALUE_UNSPECIFIED):
            daily_sleep[date]["light_minutes"] += duration
            daily_sleep[date]["total_sleep_minutes"] += duration
        elif sleep_type == SLEEP_VALUE_REM:
            daily_sleep[date]["rem_minutes"] += duration
            daily_sleep[date]["total_sleep_minutes"] += duration
        elif sleep_type == SLEEP_VALUE_AWAKE:
            daily_sleep[date]["awake_minutes"] += duration

    sleep_result = {
        date: dict(values)
        for date, values in daily_sleep.items()
        if values["total_sleep_minutes"] > 0
    }

    logger.info("Extracted data summary:")
    logger.info(f"  Weight: {len(weight_result)} days")
    logger.info(f"  Steps: {len(steps_result)} days")
    logger.info(f"  HRV: {len(hrv_result)} days")
    logger.info(f"  RHR: {len(rhr_result)} days")
    logger.info(f"  Sleep: {len(sleep_result)} days")
    logger.info(f"  Calories: {len(calories_result)} days")

    return {
        "weight": weight_result,
        "steps": steps_result,
        "hrv": hrv_result,
        "rhr": rhr_result,
        "sleep": sleep_result,
        "calories": calories_result,
        "record_count": record_count,
    }


def import_apple_health(
    user_id: int,
    zip_path: Path,
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
    dry_run: bool = False,
) -> dict[str, int | list[str]]:
    stats = ImportStats()

    if not zip_path.exists():
        stats.errors.append(f"File not found: {zip_path}")
        return stats.to_dict()

    xml_path = Path("/tmp/apple_health_export/export.xml")

    if not xml_path.exists():
        logger.info(f"Extracting {zip_path}...")
        with zipfile.ZipFile(zip_path, "r") as zf:
            for name in zf.namelist():
                if name.endswith("export.xml"):
                    zf.extract(name, "/tmp")
                    extracted = Path("/tmp") / name
                    xml_path.parent.mkdir(parents=True, exist_ok=True)
                    if extracted != xml_path:
                        extracted.rename(xml_path)
                    break

    if not xml_path.exists():
        stats.errors.append("export.xml not found in zip archive")
        return stats.to_dict()

    data = extract_data_from_xml(xml_path)
    stats.records_processed = data["record_count"]

    with get_db_session_context() as session:
        user = session.query(User).filter_by(id=user_id).first()
        if not user:
            stats.errors.append(f"User {user_id} not found")
            return stats.to_dict()

        for date, weight_value in data["weight"].items():
            if start_date and date < start_date:
                continue
            if end_date and date > end_date:
                continue

            if dry_run:
                logger.debug(f"[DRY RUN] Weight {date}: {weight_value:.1f} kg")
                continue

            existing = (
                session.query(Weight).filter_by(user_id=user_id, date=date).first()
            )
            if existing:
                if existing.weight_kg is None:
                    existing.weight_kg = weight_value
                    stats.weight_imported += 1
            else:
                session.add(Weight(user_id=user_id, date=date, weight_kg=weight_value))
                stats.weight_imported += 1

        for date, step_values in data["steps"].items():
            if start_date and date < start_date:
                continue
            if end_date and date > end_date:
                continue

            if dry_run:
                logger.debug(f"[DRY RUN] Steps {date}: {step_values['total_steps']}")
                continue

            existing = (
                session.query(Steps).filter_by(user_id=user_id, date=date).first()
            )
            if existing:
                if existing.total_steps is None or existing.total_steps == 0:
                    existing.total_steps = step_values["total_steps"]
                if existing.total_distance is None or existing.total_distance == 0:
                    existing.total_distance = step_values["total_distance"]
                if existing.floors_climbed is None or existing.floors_climbed == 0:
                    existing.floors_climbed = step_values["floors_climbed"]
                stats.steps_imported += 1
            else:
                session.add(
                    Steps(
                        user_id=user_id,
                        date=date,
                        total_steps=step_values["total_steps"],
                        total_distance=step_values["total_distance"],
                        floors_climbed=step_values["floors_climbed"],
                    )
                )
                stats.steps_imported += 1

        for date, hrv_value in data["hrv"].items():
            if start_date and date < start_date:
                continue
            if end_date and date > end_date:
                continue

            if dry_run:
                logger.debug(f"[DRY RUN] HRV {date}: {hrv_value:.1f} ms")
                continue

            existing = session.query(HRV).filter_by(user_id=user_id, date=date).first()
            if existing:
                if existing.hrv_avg is None:
                    existing.hrv_avg = hrv_value
                    stats.hrv_imported += 1
            else:
                session.add(HRV(user_id=user_id, date=date, hrv_avg=hrv_value))
                stats.hrv_imported += 1

        for date, rhr_value in data["rhr"].items():
            if start_date and date < start_date:
                continue
            if end_date and date > end_date:
                continue

            if dry_run:
                logger.debug(f"[DRY RUN] RHR {date}: {rhr_value} bpm")
                continue

            existing = (
                session.query(HeartRate).filter_by(user_id=user_id, date=date).first()
            )
            if existing:
                if existing.resting_hr is None:
                    existing.resting_hr = rhr_value
                    stats.rhr_imported += 1
            else:
                session.add(HeartRate(user_id=user_id, date=date, resting_hr=rhr_value))
                stats.rhr_imported += 1

        for date, sleep_values in data["sleep"].items():
            if start_date and date < start_date:
                continue
            if end_date and date > end_date:
                continue

            if dry_run:
                logger.debug(
                    f"[DRY RUN] Sleep {date}: {sleep_values['total_sleep_minutes']:.0f} min"
                )
                continue

            existing = (
                session.query(Sleep).filter_by(user_id=user_id, date=date).first()
            )
            if existing:
                if existing.deep_minutes is None:
                    existing.deep_minutes = sleep_values["deep_minutes"]
                if existing.light_minutes is None:
                    existing.light_minutes = sleep_values["light_minutes"]
                if existing.rem_minutes is None:
                    existing.rem_minutes = sleep_values["rem_minutes"]
                if existing.awake_minutes is None:
                    existing.awake_minutes = sleep_values["awake_minutes"]
                if existing.total_sleep_minutes is None:
                    existing.total_sleep_minutes = sleep_values["total_sleep_minutes"]
                stats.sleep_imported += 1
            else:
                session.add(
                    Sleep(
                        user_id=user_id,
                        date=date,
                        deep_minutes=sleep_values["deep_minutes"],
                        light_minutes=sleep_values["light_minutes"],
                        rem_minutes=sleep_values["rem_minutes"],
                        awake_minutes=sleep_values["awake_minutes"],
                        total_sleep_minutes=sleep_values["total_sleep_minutes"],
                    )
                )
                stats.sleep_imported += 1

        for date, cal_values in data["calories"].items():
            if start_date and date < start_date:
                continue
            if end_date and date > end_date:
                continue

            if dry_run:
                total = cal_values["active_energy"] + cal_values["basal_energy"]
                logger.debug(f"[DRY RUN] Calories {date}: {total:.0f} kcal")
                continue

            existing = (
                session.query(Energy).filter_by(user_id=user_id, date=date).first()
            )
            if existing:
                if existing.active_energy is None or existing.active_energy == 0:
                    existing.active_energy = cal_values["active_energy"]
                if existing.basal_energy is None or existing.basal_energy == 0:
                    existing.basal_energy = cal_values["basal_energy"]
                stats.calories_imported += 1
            else:
                session.add(
                    Energy(
                        user_id=user_id,
                        date=date,
                        active_energy=cal_values["active_energy"],
                        basal_energy=cal_values["basal_energy"],
                    )
                )
                stats.calories_imported += 1

        if not dry_run:
            session.commit()

            for data_type, count in [
                (DataType.WEIGHT, stats.weight_imported),
                (DataType.STEPS, stats.steps_imported),
                (DataType.HRV, stats.hrv_imported),
                (DataType.HEART_RATE, stats.rhr_imported),
                (DataType.SLEEP, stats.sleep_imported),
                (DataType.ENERGY, stats.calories_imported),
            ]:
                if count == 0:
                    continue

                sync_record = (
                    session.query(DataSync)
                    .filter_by(
                        user_id=user_id,
                        source=DataSource.APPLE_HEALTH.value,
                        data_type=data_type.value,
                    )
                    .first()
                )
                if sync_record:
                    sync_record.last_sync_date = datetime.date.today()
                    sync_record.last_sync_timestamp = datetime.datetime.utcnow()
                    sync_record.status = SyncStatus.SUCCESS.value
                    sync_record.records_synced = (
                        sync_record.records_synced or 0
                    ) + count
                else:
                    sync_record = DataSync(
                        user_id=user_id,
                        source=DataSource.APPLE_HEALTH.value,
                        data_type=data_type.value,
                        last_sync_date=datetime.date.today(),
                        last_sync_timestamp=datetime.datetime.utcnow(),
                        status=SyncStatus.SUCCESS.value,
                        records_synced=count,
                    )
                    session.add(sync_record)

            session.commit()

    logger.info(f"Import complete: {stats.to_dict()}")
    return stats.to_dict()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Import Apple Health data")
    parser.add_argument(
        "--user-id", type=int, required=True, help="User ID to import data for"
    )
    parser.add_argument(
        "--zip-path", type=str, required=True, help="Path to Apple Health export.zip"
    )
    parser.add_argument("--start-date", type=str, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", type=str, help="End date (YYYY-MM-DD)")
    parser.add_argument("--dry-run", action="store_true", help="Don't actually import")
    args = parser.parse_args()

    start_date = None
    end_date = None

    if args.start_date:
        start_date = datetime.datetime.strptime(args.start_date, "%Y-%m-%d").date()
    if args.end_date:
        end_date = datetime.datetime.strptime(args.end_date, "%Y-%m-%d").date()

    zip_path = Path(args.zip_path)

    logger.info(f"Starting Apple Health import for user {args.user_id}")
    logger.info(f"Zip path: {zip_path}")
    logger.info(f"Date range: {start_date or 'beginning'} to {end_date or 'now'}")
    logger.info(f"Dry run: {args.dry_run}")

    stats = import_apple_health(
        user_id=args.user_id,
        zip_path=zip_path,
        start_date=start_date,
        end_date=end_date,
        dry_run=args.dry_run,
    )

    print("\n=== Import Summary ===")
    print(f"Records processed: {stats['records_processed']:,}")
    print(f"Weight imported: {stats['weight_imported']}")
    print(f"Steps imported: {stats['steps_imported']}")
    print(f"HRV imported: {stats['hrv_imported']}")
    print(f"RHR imported: {stats['rhr_imported']}")
    print(f"Sleep imported: {stats['sleep_imported']}")
    print(f"Calories imported: {stats['calories_imported']}")
    if stats["errors"]:
        print(f"Errors: {len(stats['errors'])}")
        for err in stats["errors"][:10]:
            print(f"  - {err}")


if __name__ == "__main__":
    main()
