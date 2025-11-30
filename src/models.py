import datetime
from typing import Any

from sqlalchemy import (
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
from sqlalchemy.orm import declarative_base, relationship

Base: Any = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(80), unique=True, nullable=False, index=True)
    password_hash = Column(String(200), nullable=False)
    encryption_key_sealed = Column(
        Text, nullable=True
    )  # Per-user encryption key sealed with master key
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    credentials = relationship(
        "UserCredentials",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    settings = relationship(
        "UserSettings",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    sleep_data = relationship(
        "Sleep", back_populates="user", cascade="all, delete-orphan"
    )
    weight_data = relationship(
        "Weight", back_populates="user", cascade="all, delete-orphan"
    )
    heart_rate_data = relationship(
        "HeartRate", back_populates="user", cascade="all, delete-orphan"
    )
    stress_data = relationship(
        "Stress", back_populates="user", cascade="all, delete-orphan"
    )
    hrv_data = relationship("HRV", back_populates="user", cascade="all, delete-orphan")
    energy_data = relationship(
        "Energy", back_populates="user", cascade="all, delete-orphan"
    )
    steps = relationship("Steps", back_populates="user", cascade="all, delete-orphan")
    workout_sets = relationship(
        "WorkoutSet", back_populates="user", cascade="all, delete-orphan"
    )
    data_syncs = relationship(
        "DataSync", back_populates="user", cascade="all, delete-orphan"
    )
    body_battery_data = relationship(
        "BodyBattery", back_populates="user", cascade="all, delete-orphan"
    )
    whoop_recoveries = relationship(
        "WhoopRecovery", back_populates="user", cascade="all, delete-orphan"
    )
    whoop_sleeps = relationship(
        "WhoopSleep", back_populates="user", cascade="all, delete-orphan"
    )
    whoop_workouts = relationship(
        "WhoopWorkout", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<User(username={self.username})>"


class UserCredentials(Base):
    __tablename__ = "user_credentials"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    garmin_email = Column(String(200))  # Store in plain text (it's just email)
    encrypted_garmin_password = Column(String(500))  # Encrypted
    encrypted_hevy_api_key = Column(String(500))  # Encrypted
    encrypted_whoop_access_token = Column(String(1000))  # Encrypted
    encrypted_whoop_refresh_token = Column(String(1000))  # Encrypted
    whoop_token_expires_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )

    # Relationships
    user = relationship("User", back_populates="credentials")

    def __repr__(self):
        return f"<UserCredentials(user_id={self.user_id}, garmin_email={self.garmin_email})>"


class UserSettings(Base):
    __tablename__ = "user_settings"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)

    # Personalized HRV thresholds
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

    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )

    # Relationships
    user = relationship("User", back_populates="settings")

    def __repr__(self):
        return f"<UserSettings(user_id={self.user_id}, hrv_good={self.hrv_good_threshold})>"


class Sleep(Base):
    __tablename__ = "sleep"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
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
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="sleep_data")

    # Ensure unique constraint on user_id + date combination
    __table_args__ = (
        UniqueConstraint("user_id", "date", name="_user_sleep_date_uc"),
        Index(
            "idx_sleep_user_date", "user_id", "date", postgresql_ops={"date": "DESC"}
        ),
    )

    def __repr__(self):
        return f"<Sleep(user_id={self.user_id}, date={self.date}, total={self.total_sleep_minutes}min, score={self.sleep_score})>"


class HRV(Base):
    __tablename__ = "hrv"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    hrv_avg = Column(Float)
    hrv_status = Column(String(50))
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="hrv_data")

    # Ensure unique constraint on user_id + date combination
    __table_args__ = (
        UniqueConstraint("user_id", "date", name="_user_hrv_date_uc"),
        Index("idx_hrv_user_date", "user_id", "date", postgresql_ops={"date": "DESC"}),
    )

    def __repr__(self):
        return f"<HRV(user_id={self.user_id}, date={self.date}, avg={self.hrv_avg}ms, status={self.hrv_status})>"


class Weight(Base):
    __tablename__ = "weight"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    weight_kg = Column(Float)
    bmi = Column(Float)
    body_fat_pct = Column(Float)
    muscle_mass_kg = Column(Float)
    bone_mass_kg = Column(Float)
    water_pct = Column(Float)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="weight_data")

    __table_args__ = (
        UniqueConstraint("user_id", "date", name="_user_weight_date_uc"),
        Index(
            "idx_weight_user_date",
            "user_id",
            "date",
            postgresql_ops={"date": "DESC"},
        ),
    )

    def __repr__(self):
        return f"<Weight(user_id={self.user_id}, date={self.date}, weight={self.weight_kg}kg, bmi={self.bmi})>"


class HeartRate(Base):
    __tablename__ = "heart_rate"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    resting_hr = Column(Integer)
    max_hr = Column(Integer)
    avg_hr = Column(Integer)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="heart_rate_data")

    # Ensure unique constraint on user_id + date combination
    __table_args__ = (
        UniqueConstraint("user_id", "date", name="_user_heart_rate_date_uc"),
        Index(
            "idx_heart_rate_user_date",
            "user_id",
            "date",
            postgresql_ops={"date": "DESC"},
        ),
    )

    def __repr__(self):
        return f"<HeartRate(user_id={self.user_id}, date={self.date}, resting={self.resting_hr}bpm)>"


class Stress(Base):
    __tablename__ = "stress"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    avg_stress = Column(Float)  # Average stress level for the day
    max_stress = Column(Float)  # Maximum stress level
    stress_level = Column(String(20))  # low, medium, high
    rest_stress = Column(Float)  # Stress during rest periods
    activity_stress = Column(Float)  # Stress during activity
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Unique constraint on user_id and date
    __table_args__ = (
        UniqueConstraint("user_id", "date", name="unique_user_stress_date"),
        Index(
            "idx_stress_user_date", "user_id", "date", postgresql_ops={"date": "DESC"}
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
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    active_energy = Column(Float)  # Active calories burned (kcal)
    basal_energy = Column(Float)  # Basal/resting calories burned (kcal)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="energy_data")

    # Ensure uniqueness per user and date
    __table_args__ = (
        UniqueConstraint("user_id", "date", name="_user_date_energy_uc"),
        Index(
            "idx_energy_user_date", "user_id", "date", postgresql_ops={"date": "DESC"}
        ),
    )

    def __repr__(self):
        total = (self.active_energy or 0) + (self.basal_energy or 0)
        return f"<Energy(user_id={self.user_id}, date={self.date}, active={self.active_energy}kcal, basal={self.basal_energy}kcal, total={total}kcal)>"


class Steps(Base):
    __tablename__ = "steps"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    total_steps = Column(Integer)  # Total steps for the day
    total_distance = Column(Float)  # Total distance in meters
    step_goal = Column(Integer)  # Daily step goal
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="steps")

    # Ensure uniqueness per user and date
    __table_args__ = (
        UniqueConstraint("user_id", "date", name="_user_date_steps_uc"),
        Index(
            "idx_steps_user_date", "user_id", "date", postgresql_ops={"date": "DESC"}
        ),
    )

    def __repr__(self):
        return f"<Steps(user_id={self.user_id}, date={self.date}, steps={self.total_steps})>"


class WorkoutSet(Base):
    __tablename__ = "workout_sets"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    exercise = Column(String(200), nullable=False)
    weight_kg = Column(Float)
    reps = Column(Integer)
    rpe = Column(Float)  # Rate of Perceived Exertion
    set_type = Column(String(50))  # normal, warmup, failure, etc.
    duration_seconds = Column(Integer)
    distance_meters = Column(Float)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="workout_sets")

    def __repr__(self):
        return f"<WorkoutSet(user_id={self.user_id}, date={self.date}, exercise={self.exercise}, {self.weight_kg}kg x {self.reps})>"


class DataSync(Base):
    __tablename__ = "data_sync"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    source = Column(String(50), nullable=False)  # 'garmin', 'hevy', 'whoop'
    data_type = Column(String(50), nullable=False)  # 'sleep', 'hrv', 'workouts'
    last_sync_date = Column(Date)
    last_sync_timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    records_synced = Column(Integer, default=0)
    status = Column(String(20), default="success")  # 'success', 'error', 'partial'
    error_message = Column(Text)

    # Relationships
    user = relationship("User", back_populates="data_syncs")

    def __repr__(self):
        return f"<DataSync(user_id={self.user_id}, source={self.source}, type={self.data_type}, last_sync={self.last_sync_date})>"


class BodyBattery(Base):
    __tablename__ = "body_battery"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    charged = Column(Integer)
    drained = Column(Integer)
    highest = Column(Integer)
    lowest = Column(Integer)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="body_battery_data")

    __table_args__ = (
        UniqueConstraint("user_id", "date", name="_user_body_battery_date_uc"),
        Index(
            "idx_body_battery_user_date",
            "user_id",
            "date",
            postgresql_ops={"date": "DESC"},
        ),
    )

    def __repr__(self):
        return f"<BodyBattery(user_id={self.user_id}, date={self.date}, highest={self.highest}, lowest={self.lowest})>"


class WhoopRecovery(Base):
    __tablename__ = "whoop_recovery"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    recovery_score = Column(Integer)
    resting_heart_rate = Column(Integer)
    hrv_rmssd = Column(Float)
    spo2_percentage = Column(Float)
    skin_temp_celsius = Column(Float)
    user_calibrating = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="whoop_recoveries")

    __table_args__ = (
        UniqueConstraint("user_id", "date", name="_user_whoop_recovery_date_uc"),
        Index(
            "idx_whoop_recovery_user_date",
            "user_id",
            "date",
            postgresql_ops={"date": "DESC"},
        ),
    )

    def __repr__(self):
        return f"<WhoopRecovery(user_id={self.user_id}, date={self.date}, score={self.recovery_score}, hrv={self.hrv_rmssd}ms)>"


class WhoopSleep(Base):
    __tablename__ = "whoop_sleep"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
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
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="whoop_sleeps")

    __table_args__ = (
        UniqueConstraint("user_id", "date", name="_user_whoop_sleep_date_uc"),
        Index(
            "idx_whoop_sleep_user_date",
            "user_id",
            "date",
            postgresql_ops={"date": "DESC"},
        ),
    )

    def __repr__(self):
        return f"<WhoopSleep(user_id={self.user_id}, date={self.date}, performance={self.sleep_performance_percentage}%)>"


class WhoopWorkout(Base):
    __tablename__ = "whoop_workouts"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    start_time = Column(DateTime, nullable=False)
    strain = Column(Float)
    avg_heart_rate = Column(Integer)
    max_heart_rate = Column(Integer)
    kilojoules = Column(Float)
    distance_meters = Column(Float)
    altitude_gain_meters = Column(Float)
    sport_name = Column(String(100))
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="whoop_workouts")

    __table_args__ = (
        Index(
            "idx_whoop_workout_user_date",
            "user_id",
            "date",
            postgresql_ops={"date": "DESC"},
        ),
    )

    def __repr__(self):
        return f"<WhoopWorkout(user_id={self.user_id}, date={self.date}, strain={self.strain}, sport={self.sport_name})>"
