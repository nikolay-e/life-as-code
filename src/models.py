import datetime
from typing import Any, cast

from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import declarative_base, relationship, validates

from date_utils import utcnow
from enums import DataSource, SyncStatus, SyncWindow, SyncWindowStatus

Base: Any = declarative_base()

CASCADE_ALL_DELETE = "all, delete-orphan"
USERS_ID_FK = "users.id"
AVG_HR_CHECK = (
    "(avg_heart_rate >= 30 AND avg_heart_rate <= 250) OR avg_heart_rate IS NULL"
)
MAX_HR_CHECK = (
    "(max_heart_rate >= 40 AND max_heart_rate <= 250) OR max_heart_rate IS NULL"
)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(80), unique=True, nullable=False, index=True)
    password_hash = Column(String(200), nullable=False)
    encryption_key_sealed = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    # Relationships
    credentials = relationship(
        "UserCredentials",
        back_populates="user",
        uselist=False,
        cascade=CASCADE_ALL_DELETE,
    )
    settings = relationship(
        "UserSettings",
        back_populates="user",
        uselist=False,
        cascade=CASCADE_ALL_DELETE,
    )
    sleep_data = relationship(
        "Sleep", back_populates="user", cascade=CASCADE_ALL_DELETE
    )
    weight_data = relationship(
        "Weight", back_populates="user", cascade=CASCADE_ALL_DELETE
    )
    heart_rate_data = relationship(
        "HeartRate", back_populates="user", cascade=CASCADE_ALL_DELETE
    )
    stress_data = relationship(
        "Stress", back_populates="user", cascade=CASCADE_ALL_DELETE
    )
    hrv_data = relationship("HRV", back_populates="user", cascade=CASCADE_ALL_DELETE)
    energy_data = relationship(
        "Energy", back_populates="user", cascade=CASCADE_ALL_DELETE
    )
    steps = relationship("Steps", back_populates="user", cascade=CASCADE_ALL_DELETE)
    workout_sets = relationship(
        "WorkoutSet", back_populates="user", cascade=CASCADE_ALL_DELETE
    )
    data_syncs = relationship(
        "DataSync", back_populates="user", cascade=CASCADE_ALL_DELETE
    )
    sync_progress = relationship(
        "SyncProgress", back_populates="user", cascade=CASCADE_ALL_DELETE
    )
    whoop_recoveries = relationship(
        "WhoopRecovery", back_populates="user", cascade=CASCADE_ALL_DELETE
    )
    whoop_sleeps = relationship(
        "WhoopSleep", back_populates="user", cascade=CASCADE_ALL_DELETE
    )
    whoop_workouts = relationship(
        "WhoopWorkout", back_populates="user", cascade=CASCADE_ALL_DELETE
    )
    whoop_cycles = relationship(
        "WhoopCycle", back_populates="user", cascade=CASCADE_ALL_DELETE
    )
    garmin_training_status = relationship(
        "GarminTrainingStatus", back_populates="user", cascade=CASCADE_ALL_DELETE
    )
    garmin_activities = relationship(
        "GarminActivity", back_populates="user", cascade=CASCADE_ALL_DELETE
    )
    garmin_race_predictions = relationship(
        "GarminRacePrediction", back_populates="user", cascade=CASCADE_ALL_DELETE
    )
    predictions = relationship(
        "Prediction", back_populates="user", cascade=CASCADE_ALL_DELETE
    )
    anomalies = relationship(
        "Anomaly", back_populates="user", cascade=CASCADE_ALL_DELETE
    )
    health_snapshots = relationship(
        "HealthSnapshot", back_populates="user", cascade=CASCADE_ALL_DELETE
    )
    clinical_alert_events = relationship(
        "ClinicalAlertEvent", back_populates="user", cascade=CASCADE_ALL_DELETE
    )
    blood_biomarkers = relationship(
        "BloodBiomarker", back_populates="user", cascade=CASCADE_ALL_DELETE
    )
    interventions = relationship(
        "Intervention", back_populates="user", cascade=CASCADE_ALL_DELETE
    )
    functional_tests = relationship(
        "FunctionalTest", back_populates="user", cascade=CASCADE_ALL_DELETE
    )
    longevity_goals = relationship(
        "LongevityGoal", back_populates="user", cascade=CASCADE_ALL_DELETE
    )

    def __repr__(self):
        return f"<User(username={self.username})>"


class UserCredentials(Base):
    __tablename__ = "user_credentials"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey(USERS_ID_FK), nullable=False, unique=True)
    garmin_email = Column(String(200))  # Store in plain text (it's just email)
    encrypted_garmin_password = Column(String(500))  # Encrypted
    encrypted_hevy_api_key = Column(String(500))  # Encrypted
    encrypted_whoop_access_token = Column(String(1000))  # Encrypted
    encrypted_whoop_refresh_token = Column(String(1000))  # Encrypted
    whoop_token_expires_at = Column(DateTime)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    # Relationships
    user = relationship("User", back_populates="credentials")

    def __repr__(self):
        return f"<UserCredentials(user_id={self.user_id}, garmin_email={self.garmin_email})>"


class UserSettings(Base):
    __tablename__ = "user_settings"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey(USERS_ID_FK), nullable=False, unique=True)

    birth_date = Column(Date)
    gender = Column(String(10))

    hrv_good_threshold = Column(Integer, default=45)
    hrv_moderate_threshold = Column(Integer, default=35)

    # Personalized sleep thresholds (in minutes)
    deep_sleep_good_threshold = Column(Integer, default=90)
    deep_sleep_moderate_threshold = Column(Integer, default=60)

    # Personalized total sleep thresholds (in hours)
    total_sleep_good_threshold = Column(Float, default=7.5)
    total_sleep_moderate_threshold = Column(Float, default=6.5)

    # Training volume thresholds (in kg)
    training_high_volume_threshold = Column(Integer, default=5000)

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    # Relationships
    user = relationship("User", back_populates="settings")

    def __repr__(self):
        return f"<UserSettings(user_id={self.user_id}, hrv_good={self.hrv_good_threshold})>"


class Sleep(Base):
    __tablename__ = "sleep"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey(USERS_ID_FK), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    source = Column(String(50), nullable=False, default="garmin")
    deep_minutes = Column(Float)
    light_minutes = Column(Float)
    rem_minutes = Column(Float)
    awake_minutes = Column(Float)
    total_sleep_minutes = Column(Float)
    sleep_score = Column(Integer)
    # New fields for enhanced sleep tracking
    body_battery_change = Column(Integer)
    skin_temp_celsius = Column(Float)
    awake_count = Column(Integer)
    sleep_quality_score = Column(Float)
    sleep_recovery_score = Column(Float)
    spo2_avg = Column(Float)
    spo2_min = Column(Float)
    respiratory_rate = Column(Float)
    created_at = Column(DateTime, default=utcnow)

    # Relationships
    user = relationship("User", back_populates="sleep_data")

    __table_args__ = (
        UniqueConstraint(
            "user_id", "date", "source", name="_user_sleep_date_source_uc"
        ),
        Index(
            "idx_sleep_user_date", "user_id", "date", postgresql_ops={"date": "DESC"}
        ),
        CheckConstraint(
            "(deep_minutes >= 0) OR deep_minutes IS NULL", name="valid_deep_minutes"
        ),
        CheckConstraint(
            "(light_minutes >= 0) OR light_minutes IS NULL", name="valid_light_minutes"
        ),
        CheckConstraint(
            "(rem_minutes >= 0) OR rem_minutes IS NULL", name="valid_rem_minutes"
        ),
        CheckConstraint(
            "(awake_minutes >= 0) OR awake_minutes IS NULL", name="valid_awake_minutes"
        ),
        CheckConstraint(
            "(total_sleep_minutes >= 0) OR total_sleep_minutes IS NULL",
            name="valid_total_sleep",
        ),
        CheckConstraint(
            "(sleep_score >= 0 AND sleep_score <= 100) OR sleep_score IS NULL",
            name="valid_sleep_score_range",
        ),
        CheckConstraint(
            "(spo2_avg >= 50 AND spo2_avg <= 100) OR spo2_avg IS NULL",
            name="valid_spo2_avg_range",
        ),
        CheckConstraint(
            "(spo2_min >= 50 AND spo2_min <= 100) OR spo2_min IS NULL",
            name="valid_spo2_min_range",
        ),
        CheckConstraint(
            "(respiratory_rate >= 5 AND respiratory_rate <= 50) OR respiratory_rate IS NULL",
            name="valid_respiratory_rate_range",
        ),
    )

    def __repr__(self):
        return f"<Sleep(user_id={self.user_id}, date={self.date}, total={self.total_sleep_minutes}min, score={self.sleep_score})>"


class HRV(Base):
    __tablename__ = "hrv"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey(USERS_ID_FK), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    source = Column(String(50), nullable=False, default="garmin")
    hrv_avg = Column(Float)
    hrv_status = Column(String(50))
    baseline_low_ms = Column(Float)
    baseline_high_ms = Column(Float)
    feedback_phrase = Column(String(200))
    created_at = Column(DateTime, default=utcnow)

    # Relationships
    user = relationship("User", back_populates="hrv_data")

    __table_args__ = (
        UniqueConstraint("user_id", "date", "source", name="_user_hrv_date_source_uc"),
        Index("idx_hrv_user_date", "user_id", "date", postgresql_ops={"date": "DESC"}),
        CheckConstraint(
            "(hrv_avg >= 0 AND hrv_avg <= 500) OR hrv_avg IS NULL",
            name="valid_hrv_range",
        ),
        CheckConstraint(
            "(baseline_low_ms >= 0 AND baseline_low_ms <= 500) OR baseline_low_ms IS NULL",
            name="valid_baseline_low_range",
        ),
        CheckConstraint(
            "(baseline_high_ms >= 0 AND baseline_high_ms <= 500) OR baseline_high_ms IS NULL",
            name="valid_baseline_high_range",
        ),
    )

    def __repr__(self):
        return f"<HRV(user_id={self.user_id}, date={self.date}, avg={self.hrv_avg}ms, status={self.hrv_status})>"


class Weight(Base):
    __tablename__ = "weight"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey(USERS_ID_FK), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    source = Column(String(50), nullable=False, default="garmin")
    weight_kg = Column(Float)
    bmi = Column(Float)
    body_fat_pct = Column(Float)
    muscle_mass_kg = Column(Float)
    bone_mass_kg = Column(Float)
    water_pct = Column(Float)
    created_at = Column(DateTime, default=utcnow)

    # Relationships
    user = relationship("User", back_populates="weight_data")

    __table_args__ = (
        UniqueConstraint(
            "user_id", "date", "source", name="_user_weight_date_source_uc"
        ),
        Index(
            "idx_weight_user_date",
            "user_id",
            "date",
            postgresql_ops={"date": "DESC"},
        ),
        CheckConstraint(
            "(weight_kg > 0 AND weight_kg < 500) OR weight_kg IS NULL",
            name="valid_weight_range",
        ),
        CheckConstraint(
            "(bmi > 0 AND bmi < 100) OR bmi IS NULL", name="valid_bmi_range"
        ),
        CheckConstraint(
            "(body_fat_pct >= 0 AND body_fat_pct <= 100) OR body_fat_pct IS NULL",
            name="valid_body_fat_range",
        ),
        CheckConstraint(
            "(muscle_mass_kg > 0 AND muscle_mass_kg < 300) OR muscle_mass_kg IS NULL",
            name="valid_muscle_mass_range",
        ),
        CheckConstraint(
            "(water_pct >= 0 AND water_pct <= 100) OR water_pct IS NULL",
            name="valid_water_pct_range",
        ),
    )

    def __repr__(self):
        return f"<Weight(user_id={self.user_id}, date={self.date}, weight={self.weight_kg}kg, bmi={self.bmi})>"


class HeartRate(Base):
    __tablename__ = "heart_rate"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey(USERS_ID_FK), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    source = Column(String(50), nullable=False, default="garmin")
    resting_hr = Column(Integer)
    max_hr = Column(Integer)
    avg_hr = Column(Integer)
    spo2_avg = Column(Float)
    spo2_min = Column(Float)
    waking_respiratory_rate = Column(Float)
    lowest_respiratory_rate = Column(Float)
    highest_respiratory_rate = Column(Float)
    created_at = Column(DateTime, default=utcnow)

    # Relationships
    user = relationship("User", back_populates="heart_rate_data")

    __table_args__ = (
        UniqueConstraint(
            "user_id", "date", "source", name="_user_heart_rate_date_source_uc"
        ),
        Index(
            "idx_heart_rate_user_date",
            "user_id",
            "date",
            postgresql_ops={"date": "DESC"},
        ),
        CheckConstraint(
            "(resting_hr >= 20 AND resting_hr <= 200) OR resting_hr IS NULL",
            name="valid_resting_hr_range",
        ),
        CheckConstraint(
            "(max_hr >= 40 AND max_hr <= 250) OR max_hr IS NULL",
            name="valid_max_hr_range",
        ),
        CheckConstraint(
            "(avg_hr >= 30 AND avg_hr <= 220) OR avg_hr IS NULL",
            name="valid_avg_hr_range",
        ),
        CheckConstraint(
            "(spo2_avg >= 50 AND spo2_avg <= 100) OR spo2_avg IS NULL",
            name="valid_hr_spo2_avg_range",
        ),
        CheckConstraint(
            "(spo2_min >= 50 AND spo2_min <= 100) OR spo2_min IS NULL",
            name="valid_hr_spo2_min_range",
        ),
        CheckConstraint(
            "(waking_respiratory_rate >= 5 AND waking_respiratory_rate <= 50) OR waking_respiratory_rate IS NULL",
            name="valid_waking_resp_rate_range",
        ),
        CheckConstraint(
            "(lowest_respiratory_rate >= 5 AND lowest_respiratory_rate <= 50) OR lowest_respiratory_rate IS NULL",
            name="valid_lowest_resp_rate_range",
        ),
        CheckConstraint(
            "(highest_respiratory_rate >= 5 AND highest_respiratory_rate <= 50) OR highest_respiratory_rate IS NULL",
            name="valid_highest_resp_rate_range",
        ),
    )

    def __repr__(self):
        return f"<HeartRate(user_id={self.user_id}, date={self.date}, resting={self.resting_hr}bpm)>"


class Stress(Base):
    __tablename__ = "stress"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey(USERS_ID_FK), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    source = Column(String(50), nullable=False, default="garmin")
    avg_stress = Column(Float)
    max_stress = Column(Float)
    stress_level = Column(String(20))
    rest_stress = Column(Float)
    activity_stress = Column(Float)
    created_at = Column(DateTime, default=utcnow)

    __table_args__ = (
        UniqueConstraint(
            "user_id", "date", "source", name="_user_stress_date_source_uc"
        ),
        Index(
            "idx_stress_user_date", "user_id", "date", postgresql_ops={"date": "DESC"}
        ),
        CheckConstraint(
            "(avg_stress >= 0 AND avg_stress <= 100) OR avg_stress IS NULL",
            name="valid_avg_stress_range",
        ),
        CheckConstraint(
            "(max_stress >= 0 AND max_stress <= 100) OR max_stress IS NULL",
            name="valid_max_stress_range",
        ),
        CheckConstraint(
            "(rest_stress >= 0 AND rest_stress <= 100) OR rest_stress IS NULL",
            name="valid_rest_stress_range",
        ),
        CheckConstraint(
            "(activity_stress >= 0 AND activity_stress <= 100) OR activity_stress IS NULL",
            name="valid_activity_stress_range",
        ),
        CheckConstraint(
            "stress_level IN ('low', 'medium', 'high') OR stress_level IS NULL",
            name="valid_stress_level",
        ),
    )

    # Relationships
    user = relationship("User", back_populates="stress_data")

    def __repr__(self):
        return (
            f"<Stress(user_id={self.user_id}, date={self.date}, avg={self.avg_stress})>"
        )


class Energy(Base):
    __tablename__ = "energy"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey(USERS_ID_FK), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    source = Column(String(50), nullable=False, default="garmin")
    active_energy = Column(Float, default=0)
    basal_energy = Column(Float, default=0)
    created_at = Column(DateTime, default=utcnow)

    user = relationship("User", back_populates="energy_data")

    __table_args__ = (
        UniqueConstraint(
            "user_id", "date", "source", name="_user_energy_date_source_uc"
        ),
        Index(
            "idx_energy_user_date", "user_id", "date", postgresql_ops={"date": "DESC"}
        ),
        CheckConstraint(
            "(active_energy >= 0) OR active_energy IS NULL",
            name="valid_active_energy",
        ),
        CheckConstraint(
            "(basal_energy >= 0) OR basal_energy IS NULL",
            name="valid_basal_energy",
        ),
        CheckConstraint(
            "(active_energy < 50000) OR active_energy IS NULL",
            name="valid_active_energy_max",
        ),
    )

    @validates("active_energy", "basal_energy")
    def validate_energy(self, key, value):
        if value is not None and value < 0:
            raise ValueError(f"{key} must be non-negative")
        return value

    def __repr__(self):
        total = (self.active_energy or 0) + (self.basal_energy or 0)
        return f"<Energy(user_id={self.user_id}, date={self.date}, active={self.active_energy}kcal, basal={self.basal_energy}kcal, total={total}kcal)>"


class Steps(Base):
    __tablename__ = "steps"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey(USERS_ID_FK), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    source = Column(String(50), nullable=False, default="garmin")
    total_steps = Column(Integer, default=0)
    total_distance = Column(Float, default=0)
    step_goal = Column(Integer, default=10000)
    active_minutes = Column(Integer, default=0)
    floors_climbed = Column(Integer, default=0)
    created_at = Column(DateTime, default=utcnow)

    user = relationship("User", back_populates="steps")

    __table_args__ = (
        UniqueConstraint(
            "user_id", "date", "source", name="_user_steps_date_source_uc"
        ),
        Index(
            "idx_steps_user_date", "user_id", "date", postgresql_ops={"date": "DESC"}
        ),
        CheckConstraint(
            "(total_steps >= 0) OR total_steps IS NULL",
            name="valid_total_steps",
        ),
        CheckConstraint(
            "(total_distance >= 0) OR total_distance IS NULL",
            name="valid_total_distance",
        ),
        CheckConstraint(
            "(step_goal >= 0) OR step_goal IS NULL",
            name="valid_step_goal",
        ),
        CheckConstraint(
            "(active_minutes >= 0) OR active_minutes IS NULL",
            name="valid_active_minutes",
        ),
        CheckConstraint(
            "(floors_climbed >= 0) OR floors_climbed IS NULL",
            name="valid_floors_climbed",
        ),
    )

    @validates(
        "total_steps", "total_distance", "step_goal", "active_minutes", "floors_climbed"
    )
    def validate_steps_fields(self, key, value):
        if value is not None and value < 0:
            raise ValueError(f"{key} must be non-negative")
        return value

    def __repr__(self):
        return f"<Steps(user_id={self.user_id}, date={self.date}, steps={self.total_steps})>"


class WorkoutSet(Base):
    __tablename__ = "workout_sets"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey(USERS_ID_FK), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    exercise = Column(String(200), nullable=False)
    set_index = Column(Integer, nullable=False, default=0)
    weight_kg = Column(Float)
    reps = Column(Integer)
    rpe = Column(Float)  # Rate of Perceived Exertion
    set_type = Column(String(50))  # normal, warmup, failure, etc.
    duration_seconds = Column(Integer)
    distance_meters = Column(Float)
    created_at = Column(DateTime, default=utcnow)

    # Relationships
    user = relationship("User", back_populates="workout_sets")

    __table_args__ = (
        UniqueConstraint(
            "user_id", "date", "exercise", "set_index", name="_user_workout_set_uc"
        ),
        Index("idx_workout_user_date", "user_id", "date"),
        CheckConstraint("weight_kg >= 0 OR weight_kg IS NULL", name="valid_weight_kg"),
        CheckConstraint("reps >= 0 OR reps IS NULL", name="valid_reps"),
        CheckConstraint(
            "(rpe >= 1 AND rpe <= 10) OR rpe IS NULL", name="valid_rpe_range"
        ),
        CheckConstraint(
            "duration_seconds >= 0 OR duration_seconds IS NULL",
            name="valid_duration",
        ),
        CheckConstraint(
            "distance_meters >= 0 OR distance_meters IS NULL",
            name="valid_distance",
        ),
    )

    def __repr__(self):
        return f"<WorkoutSet(user_id={self.user_id}, date={self.date}, exercise={self.exercise}, {self.weight_kg}kg x {self.reps})>"


class DataSync(Base):
    __tablename__ = "data_sync"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey(USERS_ID_FK), nullable=False, index=True)
    source = Column(String(50), nullable=False)  # 'garmin', 'hevy', 'whoop'
    data_type = Column(String(50), nullable=False)  # 'sleep', 'hrv', 'workouts'
    last_sync_date = Column(Date)
    last_sync_timestamp = Column(DateTime, default=utcnow)
    records_synced = Column(Integer, default=0)
    status = Column(String(20), default="success")  # 'success', 'error', 'partial'
    error_message = Column(Text)

    # Relationships
    user = relationship("User", back_populates="data_syncs")

    __table_args__ = (
        UniqueConstraint(
            "user_id", "source", "data_type", name="_user_source_datatype_uc"
        ),
        Index("idx_datasync_user_source", "user_id", "source"),
        CheckConstraint(
            f"status IN ('{SyncStatus.SUCCESS.value}', '{SyncStatus.ERROR.value}', "
            f"'{SyncStatus.PARTIAL.value}', '{SyncStatus.IN_PROGRESS.value}') OR status IS NULL",
            name="valid_sync_status",
        ),
        CheckConstraint(
            f"source IN ('{DataSource.GARMIN.value}', '{DataSource.HEVY.value}', '{DataSource.WHOOP.value}', '{DataSource.GOOGLE.value}', '{DataSource.APPLE_HEALTH.value}')",
            name="valid_sync_source",
        ),
    )

    def __repr__(self):
        return f"<DataSync(user_id={self.user_id}, source={self.source}, type={self.data_type}, last_sync={self.last_sync_date})>"


class SyncProgress(Base):
    __tablename__ = "sync_progress"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey(USERS_ID_FK), nullable=False, index=True)
    source = Column(String(50), nullable=False)

    oldest_synced_date = Column(Date)
    newest_synced_date = Column(Date)

    current_window = Column(String(20), default=SyncWindow.DAY.value)
    window_status = Column(String(20), default=SyncWindowStatus.PENDING.value)

    day_completed = Column(Date)
    week_completed = Column(Date)
    month_completed = Column(Date)
    year_completed = Column(Date)
    full_sync_completed = Column(Date)

    last_sync_started_at = Column(DateTime)
    last_sync_completed_at = Column(DateTime)
    error_message = Column(Text)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    user = relationship("User", back_populates="sync_progress")

    __table_args__ = (
        UniqueConstraint("user_id", "source", name="_user_sync_progress_source_uc"),
        CheckConstraint(
            f"source IN ('{DataSource.GARMIN.value}', '{DataSource.HEVY.value}', '{DataSource.WHOOP.value}', '{DataSource.GOOGLE.value}', '{DataSource.APPLE_HEALTH.value}')",
            name="valid_sync_progress_source",
        ),
        CheckConstraint(
            f"current_window IN ('{SyncWindow.DAY.value}', '{SyncWindow.WEEK.value}', "
            f"'{SyncWindow.MONTH.value}', '{SyncWindow.YEAR.value}', '{SyncWindow.ALL.value}')",
            name="valid_current_window",
        ),
        CheckConstraint(
            f"window_status IN ('{SyncWindowStatus.PENDING.value}', '{SyncWindowStatus.IN_PROGRESS.value}', "
            f"'{SyncWindowStatus.COMPLETED.value}', '{SyncWindowStatus.FAILED.value}')",
            name="valid_window_status",
        ),
    )

    def __repr__(self):
        return f"<SyncProgress(user_id={self.user_id}, source={self.source}, window={self.current_window})>"

    def _normalize_window(self, window: Any) -> SyncWindow | None:
        if isinstance(window, SyncWindow):
            return window
        if isinstance(window, str):
            try:
                return SyncWindow(window)
            except ValueError:
                return None
        return None

    def get_next_window(self) -> str | None:
        window_order: list[SyncWindow] = [
            SyncWindow.DAY,
            SyncWindow.WEEK,
            SyncWindow.MONTH,
            SyncWindow.YEAR,
            SyncWindow.ALL,
        ]
        try:
            current = self._normalize_window(self.current_window)
            if current is None:
                return None
            current_index = window_order.index(current)
            if current_index < len(window_order) - 1:
                return cast(str, window_order[current_index + 1].value)
        except ValueError:
            pass
        return None

    def is_window_completed(self, window: Any) -> bool:
        normalized = self._normalize_window(window)
        if normalized is None:
            return False
        completion_map = {
            SyncWindow.DAY: self.day_completed,
            SyncWindow.WEEK: self.week_completed,
            SyncWindow.MONTH: self.month_completed,
            SyncWindow.YEAR: self.year_completed,
            SyncWindow.ALL: self.full_sync_completed,
        }
        return completion_map.get(normalized) is not None

    def mark_window_completed(self, window: Any, completed_date: datetime.date):
        normalized = self._normalize_window(window)
        if normalized is None:
            return
        completion_map = {
            SyncWindow.DAY: "day_completed",
            SyncWindow.WEEK: "week_completed",
            SyncWindow.MONTH: "month_completed",
            SyncWindow.YEAR: "year_completed",
            SyncWindow.ALL: "full_sync_completed",
        }
        attr_name = completion_map.get(normalized)
        if attr_name:
            setattr(self, attr_name, completed_date)


class WhoopRecovery(Base):
    __tablename__ = "whoop_recovery"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey(USERS_ID_FK), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    recovery_score = Column(Integer)
    resting_heart_rate = Column(Integer)
    hrv_rmssd = Column(Float)
    spo2_percentage = Column(Float)
    skin_temp_celsius = Column(Float)
    user_calibrating = Column(Integer, default=0)
    created_at = Column(DateTime, default=utcnow)

    user = relationship("User", back_populates="whoop_recoveries")

    __table_args__ = (
        UniqueConstraint("user_id", "date", name="_user_whoop_recovery_date_uc"),
        Index(
            "idx_whoop_recovery_user_date",
            "user_id",
            "date",
            postgresql_ops={"date": "DESC"},
        ),
        CheckConstraint(
            "(recovery_score >= 0 AND recovery_score <= 100) OR recovery_score IS NULL",
            name="valid_recovery_score_range",
        ),
        CheckConstraint(
            "(resting_heart_rate >= 20 AND resting_heart_rate <= 200) OR resting_heart_rate IS NULL",
            name="valid_whoop_resting_hr_range",
        ),
        CheckConstraint(
            "(hrv_rmssd >= 0 AND hrv_rmssd <= 500) OR hrv_rmssd IS NULL",
            name="valid_hrv_rmssd_range",
        ),
        CheckConstraint(
            "(spo2_percentage >= 50 AND spo2_percentage <= 100) OR spo2_percentage IS NULL",
            name="valid_whoop_spo2_range",
        ),
    )

    def __repr__(self):
        return f"<WhoopRecovery(user_id={self.user_id}, date={self.date}, score={self.recovery_score}, hrv={self.hrv_rmssd}ms)>"


class WhoopSleep(Base):
    __tablename__ = "whoop_sleep"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey(USERS_ID_FK), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    sleep_performance_percentage = Column(Float)
    sleep_consistency_percentage = Column(Float)
    sleep_efficiency_percentage = Column(Float)
    total_sleep_duration_minutes = Column(Integer)
    deep_sleep_minutes = Column(Integer)
    light_sleep_minutes = Column(Integer)
    rem_sleep_minutes = Column(Integer)
    awake_minutes = Column(Integer)
    respiratory_rate = Column(Float)
    sleep_need_baseline_minutes = Column(Integer)
    sleep_need_debt_minutes = Column(Integer)
    sleep_need_strain_minutes = Column(Integer)
    sleep_need_nap_minutes = Column(Integer)
    sleep_cycle_count = Column(Integer)
    disturbance_count = Column(Integer)
    no_data_minutes = Column(Integer)
    created_at = Column(DateTime, default=utcnow)

    user = relationship("User", back_populates="whoop_sleeps")

    __table_args__ = (
        UniqueConstraint("user_id", "date", name="_user_whoop_sleep_date_uc"),
        Index(
            "idx_whoop_sleep_user_date",
            "user_id",
            "date",
            postgresql_ops={"date": "DESC"},
        ),
        CheckConstraint(
            "(sleep_performance_percentage >= 0 AND sleep_performance_percentage <= 100) OR sleep_performance_percentage IS NULL",
            name="valid_sleep_performance_range",
        ),
        CheckConstraint(
            "(sleep_consistency_percentage >= 0 AND sleep_consistency_percentage <= 100) OR sleep_consistency_percentage IS NULL",
            name="valid_sleep_consistency_range",
        ),
        CheckConstraint(
            "(sleep_efficiency_percentage >= 0 AND sleep_efficiency_percentage <= 100) OR sleep_efficiency_percentage IS NULL",
            name="valid_sleep_efficiency_range",
        ),
        CheckConstraint(
            "(total_sleep_duration_minutes >= 0) OR total_sleep_duration_minutes IS NULL",
            name="valid_whoop_total_sleep",
        ),
        CheckConstraint(
            "(respiratory_rate >= 5 AND respiratory_rate <= 50) OR respiratory_rate IS NULL",
            name="valid_whoop_respiratory_rate",
        ),
    )

    def __repr__(self):
        return f"<WhoopSleep(user_id={self.user_id}, date={self.date}, performance={self.sleep_performance_percentage}%)>"


class WhoopWorkout(Base):
    __tablename__ = "whoop_workouts"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey(USERS_ID_FK), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    start_time = Column(DateTime, nullable=False)
    strain = Column(Float)
    avg_heart_rate = Column(Integer)
    max_heart_rate = Column(Integer)
    kilojoules = Column(Float)
    distance_meters = Column(Float)
    altitude_gain_meters = Column(Float)
    sport_name = Column(String(100))
    end_time = Column(DateTime)
    percent_recorded = Column(Float)
    altitude_change_meters = Column(Float)
    zone_zero_millis = Column(Integer)
    zone_one_millis = Column(Integer)
    zone_two_millis = Column(Integer)
    zone_three_millis = Column(Integer)
    zone_four_millis = Column(Integer)
    zone_five_millis = Column(Integer)
    created_at = Column(DateTime, default=utcnow)

    user = relationship("User", back_populates="whoop_workouts")

    __table_args__ = (
        UniqueConstraint(
            "user_id", "date", "start_time", name="_user_whoop_workout_uc"
        ),
        Index(
            "idx_whoop_workout_user_date",
            "user_id",
            "date",
            postgresql_ops={"date": "DESC"},
        ),
        CheckConstraint(
            "(strain >= 0 AND strain <= 21) OR strain IS NULL",
            name="valid_strain_range",
        ),
        CheckConstraint(AVG_HR_CHECK, name="valid_whoop_workout_avg_hr"),
        CheckConstraint(MAX_HR_CHECK, name="valid_whoop_workout_max_hr"),
        CheckConstraint(
            "(kilojoules >= 0) OR kilojoules IS NULL", name="valid_kilojoules"
        ),
        CheckConstraint(
            "(distance_meters >= 0) OR distance_meters IS NULL",
            name="valid_whoop_distance",
        ),
    )

    def __repr__(self):
        return f"<WhoopWorkout(user_id={self.user_id}, date={self.date}, strain={self.strain}, sport={self.sport_name})>"


class WhoopCycle(Base):
    __tablename__ = "whoop_cycles"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey(USERS_ID_FK), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    strain = Column(Float)
    kilojoules = Column(Float)
    avg_heart_rate = Column(Integer)
    max_heart_rate = Column(Integer)
    created_at = Column(DateTime, default=utcnow)

    user = relationship("User", back_populates="whoop_cycles")

    __table_args__ = (
        UniqueConstraint("user_id", "date", name="_user_whoop_cycle_date_uc"),
        Index(
            "idx_whoop_cycle_user_date",
            "user_id",
            "date",
            postgresql_ops={"date": "DESC"},
        ),
        CheckConstraint(
            "(strain >= 0 AND strain <= 21) OR strain IS NULL",
            name="valid_cycle_strain_range",
        ),
        CheckConstraint(
            "(kilojoules >= 0) OR kilojoules IS NULL",
            name="valid_cycle_kilojoules",
        ),
        CheckConstraint(AVG_HR_CHECK, name="valid_cycle_avg_hr"),
        CheckConstraint(MAX_HR_CHECK, name="valid_cycle_max_hr"),
    )

    def __repr__(self):
        return f"<WhoopCycle(user_id={self.user_id}, date={self.date}, strain={self.strain})>"


class GarminTrainingStatus(Base):
    __tablename__ = "garmin_training_status"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey(USERS_ID_FK), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    vo2_max = Column(Float)
    vo2_max_precise = Column(Float)
    fitness_age = Column(Integer)
    training_load_7_day = Column(Float)
    acute_training_load = Column(Float)
    training_status = Column(String(50))
    training_status_description = Column(String(200))
    primary_training_effect = Column(Float)
    anaerobic_training_effect = Column(Float)
    endurance_score = Column(Float)
    training_readiness_score = Column(Float)
    total_kilocalories = Column(Float)
    active_kilocalories = Column(Float)
    created_at = Column(DateTime, default=utcnow)

    user = relationship("User", back_populates="garmin_training_status")

    __table_args__ = (
        UniqueConstraint("user_id", "date", name="_user_garmin_training_date_uc"),
        Index(
            "idx_garmin_training_user_date",
            "user_id",
            "date",
            postgresql_ops={"date": "DESC"},
        ),
        CheckConstraint(
            "(vo2_max >= 10 AND vo2_max <= 100) OR vo2_max IS NULL",
            name="valid_vo2_max_range",
        ),
        CheckConstraint(
            "(fitness_age >= 10 AND fitness_age <= 120) OR fitness_age IS NULL",
            name="valid_fitness_age_range",
        ),
        CheckConstraint(
            "(training_load_7_day >= 0) OR training_load_7_day IS NULL",
            name="valid_training_load_7_day",
        ),
        CheckConstraint(
            "(acute_training_load >= 0) OR acute_training_load IS NULL",
            name="valid_acute_training_load",
        ),
        CheckConstraint(
            "(endurance_score >= 0 AND endurance_score <= 100) OR endurance_score IS NULL",
            name="valid_endurance_score_range",
        ),
        CheckConstraint(
            "(training_readiness_score >= 0 AND training_readiness_score <= 100) OR training_readiness_score IS NULL",
            name="valid_training_readiness_score_range",
        ),
        CheckConstraint(
            "(total_kilocalories >= 0) OR total_kilocalories IS NULL",
            name="valid_total_kilocalories",
        ),
        CheckConstraint(
            "(active_kilocalories >= 0) OR active_kilocalories IS NULL",
            name="valid_active_kilocalories",
        ),
    )

    def __repr__(self):
        return f"<GarminTrainingStatus(user_id={self.user_id}, date={self.date}, vo2_max={self.vo2_max}, fitness_age={self.fitness_age})>"


class GarminActivity(Base):
    __tablename__ = "garmin_activities"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey(USERS_ID_FK), nullable=False, index=True)
    activity_id = Column(String(50), nullable=False)
    date = Column(Date, nullable=False, index=True)
    start_time = Column(DateTime, nullable=False)
    activity_type = Column(String(100))
    activity_name = Column(String(200))
    duration_seconds = Column(Integer)
    distance_meters = Column(Float)
    avg_heart_rate = Column(Integer)
    max_heart_rate = Column(Integer)
    calories = Column(Integer)
    avg_speed_mps = Column(Float)
    max_speed_mps = Column(Float)
    elevation_gain_meters = Column(Float)
    elevation_loss_meters = Column(Float)
    avg_power_watts = Column(Float)
    max_power_watts = Column(Float)
    training_effect_aerobic = Column(Float)
    training_effect_anaerobic = Column(Float)
    vo2_max_value = Column(Float)
    hr_zone_one_seconds = Column(Integer)
    hr_zone_two_seconds = Column(Integer)
    hr_zone_three_seconds = Column(Integer)
    hr_zone_four_seconds = Column(Integer)
    hr_zone_five_seconds = Column(Integer)
    created_at = Column(DateTime, default=utcnow)

    user = relationship("User", back_populates="garmin_activities")

    __table_args__ = (
        UniqueConstraint("user_id", "activity_id", name="_user_garmin_activity_uc"),
        Index(
            "idx_garmin_activity_user_date",
            "user_id",
            "date",
            postgresql_ops={"date": "DESC"},
        ),
        CheckConstraint(
            "(duration_seconds >= 0) OR duration_seconds IS NULL",
            name="valid_garmin_duration",
        ),
        CheckConstraint(
            "(distance_meters >= 0) OR distance_meters IS NULL",
            name="valid_garmin_distance",
        ),
        CheckConstraint(AVG_HR_CHECK, name="valid_garmin_activity_avg_hr"),
        CheckConstraint(MAX_HR_CHECK, name="valid_garmin_activity_max_hr"),
        CheckConstraint(
            "(calories >= 0) OR calories IS NULL",
            name="valid_garmin_calories",
        ),
        CheckConstraint(
            "(training_effect_aerobic >= 0 AND training_effect_aerobic <= 5) OR training_effect_aerobic IS NULL",
            name="valid_garmin_te_aerobic",
        ),
        CheckConstraint(
            "(training_effect_anaerobic >= 0 AND training_effect_anaerobic <= 5) OR training_effect_anaerobic IS NULL",
            name="valid_garmin_te_anaerobic",
        ),
    )

    def __repr__(self):
        return f"<GarminActivity(user_id={self.user_id}, date={self.date}, type={self.activity_type}, duration={self.duration_seconds}s)>"


class GarminRacePrediction(Base):
    __tablename__ = "garmin_race_predictions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey(USERS_ID_FK), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    prediction_5k_seconds = Column(Integer)
    prediction_10k_seconds = Column(Integer)
    prediction_half_marathon_seconds = Column(Integer)
    prediction_marathon_seconds = Column(Integer)
    vo2_max_value = Column(Float)
    created_at = Column(DateTime, default=utcnow)

    user = relationship("User", back_populates="garmin_race_predictions")

    __table_args__ = (
        UniqueConstraint("user_id", "date", name="_user_garmin_race_pred_date_uc"),
        Index(
            "idx_garmin_race_pred_user_date",
            "user_id",
            "date",
            postgresql_ops={"date": "DESC"},
        ),
        CheckConstraint(
            "(prediction_5k_seconds > 0) OR prediction_5k_seconds IS NULL",
            name="valid_pred_5k",
        ),
        CheckConstraint(
            "(prediction_10k_seconds > 0) OR prediction_10k_seconds IS NULL",
            name="valid_pred_10k",
        ),
        CheckConstraint(
            "(prediction_half_marathon_seconds > 0) OR prediction_half_marathon_seconds IS NULL",
            name="valid_pred_half",
        ),
        CheckConstraint(
            "(prediction_marathon_seconds > 0) OR prediction_marathon_seconds IS NULL",
            name="valid_pred_marathon",
        ),
        CheckConstraint(
            "(vo2_max_value >= 10 AND vo2_max_value <= 100) OR vo2_max_value IS NULL",
            name="valid_race_pred_vo2_max",
        ),
    )

    def __repr__(self):
        return f"<GarminRacePrediction(user_id={self.user_id}, date={self.date})>"


class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey(USERS_ID_FK), nullable=False, index=True)
    metric = Column(String(50), nullable=False)
    target_date = Column(Date, nullable=False)
    horizon_days = Column(Integer, nullable=False)
    p10 = Column(Float)
    p50 = Column(Float)
    p90 = Column(Float)
    model_version = Column(String(100))
    created_at = Column(DateTime, default=utcnow)

    user = relationship("User", back_populates="predictions")

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "metric",
            "target_date",
            "horizon_days",
            name="_user_prediction_uc",
        ),
        Index("idx_prediction_user_metric", "user_id", "metric", "target_date"),
        CheckConstraint("horizon_days > 0", name="valid_horizon_days"),
    )

    def __repr__(self):
        return f"<Prediction(user_id={self.user_id}, metric={self.metric}, date={self.target_date}, p50={self.p50})>"


class Anomaly(Base):
    __tablename__ = "anomalies"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey(USERS_ID_FK), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    anomaly_score = Column(Float, nullable=False)
    contributing_factors = Column(JSON)
    model_version = Column(String(100))
    created_at = Column(DateTime, default=utcnow)

    user = relationship("User", back_populates="anomalies")

    __table_args__ = (
        UniqueConstraint("user_id", "date", name="_user_anomaly_date_uc"),
        Index(
            "idx_anomaly_user_date",
            "user_id",
            "date",
            postgresql_ops={"date": "DESC"},
        ),
        CheckConstraint(
            "anomaly_score >= 0 AND anomaly_score <= 1",
            name="valid_anomaly_score",
        ),
    )

    def __repr__(self):
        return f"<Anomaly(user_id={self.user_id}, date={self.date}, score={self.anomaly_score})>"


class HealthSnapshot(Base):
    __tablename__ = "health_snapshots"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey(USERS_ID_FK), nullable=False, index=True)
    date = Column(Date, nullable=False)
    mode = Column(String(20), nullable=False, default="recent")
    snapshot_json = Column(JSON, nullable=False)
    health_score = Column(Float)
    computed_at = Column(DateTime, nullable=False, default=utcnow)

    user = relationship("User", back_populates="health_snapshots")

    __table_args__ = (
        UniqueConstraint("user_id", "date", "mode", name="_user_snapshot_date_mode_uc"),
        Index(
            "idx_snapshot_user_date",
            "user_id",
            "date",
            postgresql_ops={"date": "DESC"},
        ),
        CheckConstraint(
            "mode IN ('recent', 'quarter', 'year', 'all')",
            name="valid_snapshot_mode",
        ),
    )

    def __repr__(self):
        return f"<HealthSnapshot(user_id={self.user_id}, date={self.date}, mode={self.mode}, score={self.health_score})>"


class ClinicalAlertEvent(Base):
    __tablename__ = "clinical_alert_events"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey(USERS_ID_FK), nullable=False, index=True)
    alert_type = Column(String(50), nullable=False)
    severity = Column(String(20), nullable=False, default="warning")
    status = Column(String(20), nullable=False, default="open")
    details_json = Column(JSON)
    first_detected_at = Column(DateTime, nullable=False, default=utcnow)
    last_detected_at = Column(DateTime, nullable=False, default=utcnow)
    acknowledged_at = Column(DateTime)
    resolved_at = Column(DateTime)
    created_at = Column(DateTime, default=utcnow)

    user = relationship("User", back_populates="clinical_alert_events")

    __table_args__ = (
        Index("idx_alert_user_status", "user_id", "status"),
        Index("idx_alert_user_type", "user_id", "alert_type"),
        CheckConstraint(
            "severity IN ('info', 'warning', 'alert', 'critical')",
            name="valid_alert_severity",
        ),
        CheckConstraint(
            "status IN ('open', 'acknowledged', 'resolved')",
            name="valid_alert_status",
        ),
    )


class BloodBiomarker(Base):
    __tablename__ = "blood_biomarkers"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey(USERS_ID_FK), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    marker_name = Column(String(100), nullable=False)
    value = Column(Float, nullable=False)
    unit = Column(String(50), nullable=False)
    reference_range_low = Column(Float)
    reference_range_high = Column(Float)
    longevity_optimal_low = Column(Float)
    longevity_optimal_high = Column(Float)
    lab_name = Column(String(200))
    notes = Column(Text)
    created_at = Column(DateTime, default=utcnow)

    user = relationship("User", back_populates="blood_biomarkers")

    __table_args__ = (
        UniqueConstraint(
            "user_id", "date", "marker_name", name="_user_biomarker_date_marker_uc"
        ),
        Index("idx_biomarker_user_date", "user_id", "date"),
        Index("idx_biomarker_user_marker", "user_id", "marker_name"),
    )


class Intervention(Base):
    __tablename__ = "interventions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey(USERS_ID_FK), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    category = Column(String(50), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date)
    dosage = Column(String(100))
    frequency = Column(String(100))
    target_metrics = Column(JSON)
    notes = Column(Text)
    active = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    user = relationship("User", back_populates="interventions")

    __table_args__ = (
        Index("idx_intervention_user_active", "user_id", "active"),
        CheckConstraint(
            "category IN ('supplement', 'protocol', 'medication', 'lifestyle', 'diet')",
            name="valid_intervention_category",
        ),
        CheckConstraint(
            "active IN (0, 1)",
            name="valid_intervention_active",
        ),
    )


class FunctionalTest(Base):
    __tablename__ = "functional_tests"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey(USERS_ID_FK), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    test_name = Column(String(100), nullable=False)
    value = Column(Float, nullable=False)
    unit = Column(String(50), nullable=False)
    notes = Column(Text)
    created_at = Column(DateTime, default=utcnow)

    user = relationship("User", back_populates="functional_tests")

    __table_args__ = (
        UniqueConstraint(
            "user_id", "date", "test_name", name="_user_functest_date_name_uc"
        ),
        Index("idx_functest_user_date", "user_id", "date"),
        Index("idx_functest_user_test", "user_id", "test_name"),
    )


class LongevityGoal(Base):
    __tablename__ = "longevity_goals"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey(USERS_ID_FK), nullable=False, index=True)
    category = Column(String(100), nullable=False)
    description = Column(Text, nullable=False)
    target_value = Column(Float)
    current_value = Column(Float)
    unit = Column(String(50))
    target_age = Column(Integer)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    user = relationship("User", back_populates="longevity_goals")

    __table_args__ = (Index("idx_longevity_goal_user", "user_id"),)
