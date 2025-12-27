from enum import StrEnum


class DataSource(StrEnum):
    GARMIN = "garmin"
    HEVY = "hevy"
    WHOOP = "whoop"
    GOOGLE = "google"


class SyncStatus(StrEnum):
    SUCCESS = "success"
    ERROR = "error"
    PARTIAL = "partial"
    IN_PROGRESS = "in_progress"


class DataType(StrEnum):
    SLEEP = "sleep"
    HRV = "hrv"
    WEIGHT = "weight"
    HEART_RATE = "heart_rate"
    STRESS = "stress"
    STEPS = "steps"
    ENERGY = "energy"
    BODY_BATTERY = "body_battery"
    WORKOUTS = "workouts"
    RECOVERY = "recovery"
    CYCLES = "cycles"
    TRAINING_STATUS = "training_status"


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
