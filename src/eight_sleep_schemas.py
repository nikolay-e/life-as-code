import datetime

from pydantic import BaseModel

from date_utils import parse_iso_date
from logging_config import get_logger

logger = get_logger(__name__)


class EightSleepSessionData(BaseModel):
    date: datetime.date
    source: str = "eight_sleep"
    score: int | None = None
    sleep_duration_seconds: int | None = None
    light_duration_seconds: int | None = None
    deep_duration_seconds: int | None = None
    rem_duration_seconds: int | None = None
    tnt: int | None = None
    heart_rate: float | None = None
    hrv: float | None = None
    respiratory_rate: float | None = None
    latency_asleep_seconds: int | None = None
    latency_out_seconds: int | None = None
    bed_temp_celsius: float | None = None
    room_temp_celsius: float | None = None
    sleep_fitness_score: int | None = None
    sleep_routine_score: int | None = None
    sleep_quality_score: int | None = None

    @classmethod
    def _safe_int(cls, value) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    @classmethod
    def _safe_float(cls, value) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    @classmethod
    def _nested_current(cls, parent: dict, key: str) -> float | None:
        sub = parent.get(key, {})
        if not sub or not isinstance(sub, dict):
            return None
        return cls._safe_float(sub.get("current"))

    @classmethod
    def _avg_timeseries(cls, sessions: list, key: str) -> float | None:
        values = []
        for sess in sessions:
            ts = sess.get("timeseries", {})
            for point in ts.get(key, []):
                if isinstance(point, list) and len(point) == 2 and point[1] is not None:
                    values.append(float(point[1]))
        if not values:
            return None
        return round(sum(values) / len(values), 2)

    _logged_shape: bool = False

    @classmethod
    def from_api_response(cls, day: dict) -> "EightSleepSessionData | None":
        try:
            day_str = day.get("day")
            if not day_str:
                return None
            session_date = parse_iso_date(day_str)

            if not cls._logged_shape:
                cls._logged_shape = True
                fitness_field = day.get("sleepFitnessScore")
                health_field = day.get("health")
                logger.info(
                    "eight_sleep_payload_shape",
                    day_keys=sorted(day.keys()),
                    fitness_type=type(fitness_field).__name__,
                    fitness_keys=(
                        sorted(fitness_field.keys())
                        if isinstance(fitness_field, dict)
                        else None
                    ),
                    health_type=type(health_field).__name__,
                    health_keys=(
                        sorted(health_field.keys())
                        if isinstance(health_field, dict)
                        else None
                    ),
                )

            quality = day.get("sleepQualityScore") or {}
            routine = day.get("sleepRoutineScore") or {}
            sessions = day.get("sessions") or []

            hr = cls._nested_current(quality, "heartRate")
            hrv = cls._nested_current(quality, "hrv")
            resp = cls._nested_current(quality, "respiratoryRate")

            if hr is None and sessions:
                hr = cls._avg_timeseries(sessions, "heartRate")
            if resp is None and sessions:
                resp = cls._avg_timeseries(sessions, "respiratoryRate")

            bed_temp = cls._avg_timeseries(sessions, "tempBedC") if sessions else None
            room_temp = cls._avg_timeseries(sessions, "tempRoomC") if sessions else None

            latency_asleep = cls._nested_current(routine, "latencyAsleepSeconds")
            latency_out = cls._nested_current(routine, "latencyOutSeconds")

            # Eight Sleep returns sleepFitnessScore in one of three shapes:
            #   1. day["sleepFitnessScore"]["total"]  — current API, mirroring
            #      sleepRoutineScore / sleepQualityScore structure.
            #   2. day["sleepFitnessScore"]           — flat scalar.
            #   3. day["health"]["sleepFitnessScore"] — legacy nesting we used
            #      to read exclusively (always NULL on current API).
            # Try them in that order so we capture the value regardless of which
            # shape the upstream is currently emitting.
            fitness_raw = day.get("sleepFitnessScore")
            if isinstance(fitness_raw, dict):
                fitness_score = cls._safe_int(fitness_raw.get("total"))
            else:
                fitness_score = cls._safe_int(fitness_raw)
            if fitness_score is None:
                health = day.get("health") or {}
                fitness_score = cls._safe_int(health.get("sleepFitnessScore"))

            return cls(
                date=session_date,
                score=cls._safe_int(day.get("score")),
                sleep_duration_seconds=cls._safe_int(day.get("sleepDuration")),
                light_duration_seconds=cls._safe_int(day.get("lightDuration")),
                deep_duration_seconds=cls._safe_int(day.get("deepDuration")),
                rem_duration_seconds=cls._safe_int(day.get("remDuration")),
                tnt=cls._safe_int(day.get("tnt")),
                heart_rate=hr,
                hrv=hrv,
                respiratory_rate=resp,
                latency_asleep_seconds=cls._safe_int(latency_asleep),
                latency_out_seconds=cls._safe_int(latency_out),
                bed_temp_celsius=bed_temp,
                room_temp_celsius=room_temp,
                sleep_fitness_score=fitness_score,
                sleep_routine_score=cls._safe_int(routine.get("total")),
                sleep_quality_score=cls._safe_int(quality.get("total")),
            )
        except Exception as e:
            logger.warning("eight_sleep_session_parse_error", error=str(e))
            return None
