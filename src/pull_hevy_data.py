import datetime

from dotenv import load_dotenv
from pydantic import BaseModel
from sqlalchemy import select

from database import get_db_session_context
from date_utils import parse_iso_date, utcnow
from enums import DataSource, DataType
from errors import CredentialsDecryptionError, CredentialsNotFoundError
from http_client import HTTPClient
from logging_config import get_logger
from models import ExerciseTemplate, WorkoutSet
from sync_manager import (
    extract_and_parse,
    get_provider_credentials,
    get_sync_date_range,
)

load_dotenv()

logger = get_logger(__name__)

MAX_RETRIES = 3
REQUEST_TIMEOUT = 30


class HevyWorkoutData(BaseModel):
    date: datetime.date
    exercise: str
    # Stable Hevy exercise template id (same id space as /v1/exercise_templates).
    # Stored on every set so logged workouts can be reconciled with programmed
    # exercises by id rather than by title.
    exercise_template_id: str | None = None
    set_index: int = 0
    weight_kg: float | None = None
    reps: int | None = None
    rpe: float | None = None
    set_type: str | None = None
    duration_seconds: int | None = None
    distance_meters: float | None = None

    @staticmethod
    def _validate_rpe(rpe: float | None) -> float | None:
        if rpe is None:
            return None
        if rpe < 1 or rpe > 10:
            return None
        return rpe

    @staticmethod
    def _validate_reps(reps: int | None) -> int | None:
        if reps is None:
            return None
        if reps < 0:
            return None
        return reps

    @classmethod
    def from_api_response(cls, workout_data: dict) -> list["HevyWorkoutData"]:
        workout_sets = []
        set_counters: dict[tuple, int] = {}

        try:
            workout_date = parse_iso_date(workout_data["start_time"])

            for exercise in workout_data.get("exercises", []):
                exercise_name = exercise.get("title", "Unknown Exercise")
                template_id_raw = exercise.get("exercise_template_id")
                template_id = (
                    str(template_id_raw) if template_id_raw is not None else None
                )

                for set_data in exercise.get("sets", []):
                    try:
                        key = (workout_date, exercise_name)
                        set_index = set_counters.get(key, 0)
                        set_counters[key] = set_index + 1

                        workout_set = cls(
                            date=workout_date,
                            exercise=exercise_name,
                            exercise_template_id=template_id,
                            set_index=set_index,
                            weight_kg=set_data.get("weight_kg"),
                            reps=cls._validate_reps(set_data.get("reps")),
                            rpe=cls._validate_rpe(set_data.get("rpe")),
                            set_type=set_data.get("set_type", "normal"),
                            duration_seconds=set_data.get("duration_seconds"),
                            distance_meters=set_data.get("distance_meters"),
                        )
                        workout_sets.append(workout_set)

                    except (ValueError, TypeError, KeyError) as e:
                        logger.warning("hevy_workout_set_parse_error", error=str(e))
                        continue

        except (KeyError, ValueError, TypeError) as e:
            logger.error("hevy_workout_data_parse_error", error=str(e))

        return workout_sets


class HevyAPIClient:
    def __init__(self, api_key: str):
        self._client = HTTPClient(
            base_url="https://api.hevyapp.com/v1",
            headers={"api-key": api_key, "Accept": "application/json"},
            timeout=REQUEST_TIMEOUT,
            max_retries=MAX_RETRIES,
            rate_limit_delay=0.5,
        )

    def _fetch_page(self, page: int) -> dict | list | None:
        return self._client.get(  # type: ignore[no-any-return]
            "workouts", params={"page": page, "pageSize": 10}
        )

    def _filter_workouts_by_date(
        self, workouts: list[dict], start_date: datetime.date
    ) -> tuple[list[dict], bool]:
        filtered = []
        oldest_in_page: datetime.date | None = None
        for w in workouts:
            try:
                workout_date = parse_iso_date(w["start_time"])
                if oldest_in_page is None or workout_date < oldest_in_page:
                    oldest_in_page = workout_date
                if workout_date >= start_date:
                    filtered.append(w)
            except (KeyError, ValueError):
                filtered.append(w)
        reached_cutoff = bool(oldest_in_page and oldest_in_page < start_date)
        return filtered, reached_cutoff

    def _process_page_response(
        self,
        page_data: dict | list | None,
        start_date: datetime.date | None,
        page: int,
        all_workouts: list[dict],
    ) -> bool:
        if page_data is None:
            logger.info("hevy_page_not_found", page=page)
            return False

        if not isinstance(page_data, dict):
            logger.error("hevy_unexpected_response_type", page=page)
            return False

        workouts = page_data.get("workouts", [])

        if not workouts:
            logger.info("hevy_pagination_end")
            return False

        if start_date:
            workouts, reached_cutoff = self._filter_workouts_by_date(
                workouts, start_date
            )
            all_workouts.extend(workouts)
            if reached_cutoff:
                logger.info("hevy_date_cutoff", cutoff_date=start_date)
                return False
        else:
            all_workouts.extend(workouts)

        logger.info("hevy_page_retrieved", workouts=len(workouts), page=page)
        return True

    def get_exercise_templates(self) -> list[dict]:
        """Fetch all exercise templates (Hevy library + user customs).

        Hevy paginates this endpoint similar to /workouts. We follow until an
        empty page; max_pages bounds runaway loops.
        """
        all_templates: list[dict] = []
        page = 1
        max_pages = 200

        while page <= max_pages:
            try:
                page_data = self._client.get(
                    "exercise_templates", params={"page": page, "pageSize": 100}
                )
            except (ValueError, KeyError) as e:
                logger.error(
                    "hevy_exercise_templates_fetch_error", page=page, error=str(e)
                )
                break

            if not isinstance(page_data, dict):
                logger.warning("hevy_exercise_templates_unexpected_response", page=page)
                break

            templates = page_data.get("exercise_templates", [])
            if not templates:
                break

            all_templates.extend(templates)
            logger.info("hevy_exercise_templates_page", page=page, count=len(templates))
            page += 1

        logger.info("hevy_exercise_templates_fetch_complete", total=len(all_templates))
        return all_templates

    def get_workouts(self, start_date: datetime.date | None = None) -> list[dict]:
        all_workouts: list[dict] = []
        page = 1
        max_pages = 1000

        while page <= max_pages:
            logger.info("hevy_fetching_page", page=page)
            try:
                page_data = self._fetch_page(page)
                should_continue = self._process_page_response(
                    page_data, start_date, page, all_workouts
                )
                if not should_continue:
                    break
            except (ValueError, KeyError) as e:
                logger.error("hevy_fetch_error", page=page, error=str(e))
                break

            page += 1

        logger.info("hevy_fetch_complete", total_workouts=len(all_workouts))
        return all_workouts


def sync_hevy_data_for_user(
    user_id: int, days: int = 90, full_sync: bool = False
) -> dict:
    try:
        creds = get_provider_credentials(user_id, DataSource.HEVY)
    except (CredentialsNotFoundError, CredentialsDecryptionError) as e:
        logger.error("hevy_credentials_error", user_id=user_id, error=str(e))
        return {"error": str(e), "user_id": user_id}

    if not creds.hevy_api_key:
        return {"error": "Hevy API key not configured", "user_id": user_id}

    try:
        api_client = HevyAPIClient(creds.hevy_api_key)
        date_range = get_sync_date_range(days, full_sync)
        start_date = None if full_sync else date_range.start_date

        logger.info(
            "hevy_sync_started",
            user_id=user_id,
            sync_type=date_range.sync_type,
            start_date=start_date,
            end_date=date_range.end_date,
            full_sync=full_sync,
        )

        sync_result = extract_and_parse(
            api_call_func=lambda: api_client.get_workouts(start_date=start_date),
            parser_class=HevyWorkoutData,
            model_class=WorkoutSet,
            unique_fields=["date", "exercise", "set_index"],
            user_id=user_id,
            source=DataSource.HEVY,
            data_type=DataType.WORKOUTS,
        )

        summary = {
            "user_id": user_id,
            "sync_date": utcnow().isoformat(),
            "sync_type": date_range.sync_type,
            "source": "hevy",
            "data_type": "workouts",
            "success": sync_result.success,
            "records_processed": sync_result.records_processed,
            "records_created": sync_result.records_created,
            "records_updated": sync_result.records_updated,
            "records_skipped": sync_result.records_skipped,
            "errors": sync_result.errors[:5],
            "error_count": len(sync_result.errors),
        }

        logger.info(
            "hevy_sync_completed",
            user_id=user_id,
            records_processed=summary["records_processed"],
            records_created=summary["records_created"],
            success=summary["success"],
        )
        return summary

    except Exception as e:  # catch-all for sync resilience
        logger.error("hevy_sync_failed", user_id=user_id, error=str(e))
        return {"error": str(e), "user_id": user_id}


def sync_hevy_exercise_templates_for_user(user_id: int) -> dict:
    """Pull the user's Hevy exercise template catalog and upsert into the DB.

    Idempotent: keyed on (user_id, hevy_template_id). Custom user templates
    flagged via is_custom from Hevy's response.
    """
    try:
        creds = get_provider_credentials(user_id, DataSource.HEVY)
    except (CredentialsNotFoundError, CredentialsDecryptionError) as e:
        logger.error(
            "hevy_exercise_templates_credentials_error",
            user_id=user_id,
            error=str(e),
        )
        return {"error": str(e), "user_id": user_id}

    if not creds.hevy_api_key:
        return {"error": "Hevy API key not configured", "user_id": user_id}

    try:
        api_client = HevyAPIClient(creds.hevy_api_key)
        templates = api_client.get_exercise_templates()
    except Exception as e:
        logger.error(
            "hevy_exercise_templates_fetch_failed", user_id=user_id, error=str(e)
        )
        return {"error": str(e), "user_id": user_id}

    created = 0
    updated = 0

    with get_db_session_context() as db:
        for tpl in templates:
            hevy_id = tpl.get("id")
            title = tpl.get("title")
            if not hevy_id or not title:
                continue

            existing = db.scalars(
                select(ExerciseTemplate).filter_by(
                    user_id=user_id, hevy_template_id=str(hevy_id)
                )
            ).first()

            secondary = tpl.get("secondary_muscle_groups") or []
            if isinstance(secondary, str):
                secondary = [secondary]

            payload = {
                "title": title,
                "exercise_type": tpl.get("type") or tpl.get("exercise_type"),
                "primary_muscle_group": tpl.get("primary_muscle_group"),
                "secondary_muscle_groups": secondary,
                "equipment": tpl.get("equipment"),
                "is_custom": bool(tpl.get("is_custom", False)),
            }

            if existing is None:
                db.add(
                    ExerciseTemplate(
                        user_id=user_id,
                        hevy_template_id=str(hevy_id),
                        **payload,
                    )
                )
                created += 1
            else:
                for k, v in payload.items():
                    setattr(existing, k, v)
                updated += 1

        db.commit()

    logger.info(
        "hevy_exercise_templates_sync_completed",
        user_id=user_id,
        created=created,
        updated=updated,
        total=len(templates),
    )
    return {
        "user_id": user_id,
        "fetched": len(templates),
        "created": created,
        "updated": updated,
        "synced_at": utcnow().isoformat(),
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        user_id = int(sys.argv[1])
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 90
        full_sync = "--full" in sys.argv

        result = sync_hevy_data_for_user(user_id, days, full_sync=full_sync)
        print(f"Sync result: {result}")
    else:
        print("Usage: python pull_hevy_data.py <user_id> [days] [--full]")
