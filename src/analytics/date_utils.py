from __future__ import annotations

import os
import re
from datetime import date, datetime, timedelta, timezone

from .types import DataPoint

_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def to_day_key(date_str: str) -> str:
    if "T" in date_str:
        try:
            dt = datetime.fromisoformat(date_str)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            pass
    if " " in date_str:
        candidate = date_str.split(" ")[0]
    else:
        candidate = date_str[:10]
    if not _DATE_RE.fullmatch(candidate):
        raise ValueError(f"Cannot parse date key from: {date_str!r}")
    return candidate


def to_day_date(day_key: str) -> date:
    return date.fromisoformat(day_key[:10])


def day_number(date_str: str) -> int:
    d = to_day_date(to_day_key(date_str))
    return d.toordinal()


def local_today() -> date:
    offset_hours = int(os.getenv("BOT_TIMEZONE_OFFSET_HOURS", "0"))
    tz = timezone(timedelta(hours=offset_hours))
    return datetime.now(tz).date()


def filter_by_window(
    data: list[DataPoint], window_days: int, ref_date: date | None = None
) -> list[DataPoint]:
    today = ref_date or local_today()
    window_start = today - timedelta(days=window_days - 1)
    result = []
    for d in data:
        dk = to_day_date(to_day_key(d.date))
        if window_start <= dk <= today:
            result.append(d)
    return result


def filter_by_window_range(
    data: list[DataPoint],
    days_back: int,
    days_back_end: int,
    ref_date: date | None = None,
) -> list[DataPoint]:
    today = ref_date or local_today()
    window_start = today - timedelta(days=days_back - 1)
    window_end = today - timedelta(days=days_back_end)
    result = []
    for d in data:
        dk = to_day_date(to_day_key(d.date))
        if window_start <= dk < window_end:
            result.append(d)
    return result


def dates_in_window(window_days: int, ref_date: date | None = None) -> set[str]:
    today = ref_date or local_today()
    window_start = today - timedelta(days=window_days - 1)
    dates: set[str] = set()
    current = window_start
    while current <= today:
        dates.add(current.isoformat())
        current += timedelta(days=1)
    return dates
