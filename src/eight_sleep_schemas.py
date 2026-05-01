import datetime

from pydantic import BaseModel

from date_utils import parse_iso_date
from logging_config import get_logger

logger = get_logger(__name__)

# Module-level flag — Pydantic v2 reserves `_underscore_attrs` so it cannot live
# as a regular class attribute on the BaseModel below.
_payload_shape_logged: bool = False


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
    sleep_start_time: datetime.datetime | None = None
    sleep_end_time: datetime.datetime | None = None

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

    @classmethod
    def _log_payload_shape_once(cls, day: dict) -> None:
        global _payload_shape_logged
        if _payload_shape_logged:
            return
        _payload_shape_logged = True
        fitness_field = day.get("sleepFitnessScore")
        health_field = day.get("health")
        # WARNING level so it appears in production logs even when
        # LOG_LEVEL=WARNING (default in life-as-code prod) drops INFO.
        # This is a one-shot diagnostic per pod restart.
        logger.warning(
            "eight_sleep_payload_shape",
            day_keys=sorted(day.keys()),
            fitness_type=type(fitness_field).__name__,
            fitness_keys=(
                sorted(fitness_field.keys())
                if isinstance(fitness_field, dict)
                else None
            ),
            fitness_value_preview=(
                str(fitness_field)[:200] if fitness_field is not None else None
            ),
            health_type=type(health_field).__name__,
            health_keys=(
                sorted(health_field.keys()) if isinstance(health_field, dict) else None
            ),
        )

    @classmethod
    def _extract_fitness_score(cls, day: dict) -> int | None:
        # Eight Sleep returns sleepFitnessScore in one of three shapes:
        #   1. day["sleepFitnessScore"]["total"]  — current API, mirroring
        #      sleepRoutineScore / sleepQualityScore structure.
        #   2. day["sleepFitnessScore"]           — flat scalar.
        #   3. day["health"]["sleepFitnessScore"] — legacy nesting we used
        #      to read exclusively (always NULL on current API).
        fitness_raw = day.get("sleepFitnessScore")
        if isinstance(fitness_raw, dict):
            score = cls._safe_int(fitness_raw.get("total"))
        else:
            score = cls._safe_int(fitness_raw)
        if score is not None:
            return score
        health = day.get("health") or {}
        return cls._safe_int(health.get("sleepFitnessScore"))

    @classmethod
    def _extract_heart_metrics(
        cls, quality: dict, sessions: list
    ) -> tuple[float | None, float | None, float | None]:
        hr = cls._nested_current(quality, "heartRate")
        hrv = cls._nested_current(quality, "hrv")
        resp = cls._nested_current(quality, "respiratoryRate")
        if hr is None and sessions:
            hr = cls._avg_timeseries(sessions, "heartRate")
        if resp is None and sessions:
            resp = cls._avg_timeseries(sessions, "respiratoryRate")
        return hr, hrv, resp

    @classmethod
    def _extract_temps(cls, sessions: list) -> tuple[float | None, float | None]:
        if not sessions:
            return None, None
        return (
            cls._avg_timeseries(sessions, "tempBedC"),
            cls._avg_timeseries(sessions, "tempRoomC"),
        )

    @classmethod
    def _parse_iso_utc(cls, value) -> datetime.datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime.datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=datetime.UTC)
            return value
        if isinstance(value, (int, float)):
            try:
                return datetime.datetime.fromtimestamp(float(value), tz=datetime.UTC)
            except (ValueError, OSError, OverflowError):
                return None
        if not isinstance(value, str):
            return None
        try:
            cleaned = value.replace("Z", "+00:00")
            parsed = datetime.datetime.fromisoformat(cleaned)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=datetime.UTC)
            return parsed
        except ValueError:
            return None

    @classmethod
    def _extract_sleep_window(
        cls, day: dict, sessions: list
    ) -> tuple[datetime.datetime | None, datetime.datetime | None]:
        # Day-level presenceStart/presenceEnd are the canonical bedtime fields
        # (Eight Sleep aggregates per-side presence at the day level).
        start = cls._parse_iso_utc(day.get("presenceStart"))
        end = cls._parse_iso_utc(day.get("presenceEnd"))
        if start is not None and end is not None:
            return start, end

        # Fallback: derive from earliest start / latest end across sessions.
        session_starts: list[datetime.datetime] = []
        session_ends: list[datetime.datetime] = []
        for sess in sessions:
            if not isinstance(sess, dict):
                continue
            for key in ("presenceStart", "tsStart", "startTime", "start"):
                ts = cls._parse_iso_utc(sess.get(key))
                if ts is not None:
                    session_starts.append(ts)
                    break
            for key in ("presenceEnd", "tsEnd", "endTime", "end"):
                ts = cls._parse_iso_utc(sess.get(key))
                if ts is not None:
                    session_ends.append(ts)
                    break

        if start is None and session_starts:
            start = min(session_starts)
        if end is None and session_ends:
            end = max(session_ends)
        return start, end

    @classmethod
    def from_api_response(cls, day: dict) -> "EightSleepSessionData | None":
        try:
            day_str = day.get("day")
            if not day_str:
                return None
            session_date = parse_iso_date(day_str)

            cls._log_payload_shape_once(day)

            quality = day.get("sleepQualityScore") or {}
            routine = day.get("sleepRoutineScore") or {}
            sessions = day.get("sessions") or []

            hr, hrv, resp = cls._extract_heart_metrics(quality, sessions)
            bed_temp, room_temp = cls._extract_temps(sessions)
            latency_asleep = cls._nested_current(routine, "latencyAsleepSeconds")
            latency_out = cls._nested_current(routine, "latencyOutSeconds")
            sleep_start, sleep_end = cls._extract_sleep_window(day, sessions)

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
                sleep_fitness_score=cls._extract_fitness_score(day),
                sleep_routine_score=cls._safe_int(routine.get("total")),
                sleep_quality_score=cls._safe_int(quality.get("total")),
                sleep_start_time=sleep_start,
                sleep_end_time=sleep_end,
            )
        except Exception as e:
            logger.warning("eight_sleep_session_parse_error", error=str(e))
            return None
