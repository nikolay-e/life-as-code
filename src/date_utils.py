import datetime


def utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC).replace(tzinfo=None)


def parse_iso_datetime(iso_string: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(iso_string.replace("Z", "+00:00"))


def parse_iso_date(iso_string: str) -> datetime.date:
    return datetime.date.fromisoformat(iso_string[:10])


def parse_date_string(date_string: str) -> datetime.date:
    return datetime.datetime.strptime(date_string, "%Y-%m-%d").date()
