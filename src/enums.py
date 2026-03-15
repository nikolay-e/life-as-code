from enum import StrEnum


class DataSource(StrEnum):
    GARMIN = "garmin"
    HEVY = "hevy"
    WHOOP = "whoop"
    GOOGLE = "google"
    APPLE_HEALTH = "apple_health"


class SyncStatus(StrEnum):
    SUCCESS = "success"
    ERROR = "error"
    PARTIAL = "partial"
    IN_PROGRESS = "in_progress"


class DataType(StrEnum):
    SLEEP = "sleep"
    WORKOUTS = "workouts"
    RECOVERY = "recovery"
    CYCLES = "cycles"


class SyncWindow(StrEnum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"
    ALL = "all"


class SyncWindowStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
