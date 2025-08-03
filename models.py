"""
SQLAlchemy models for Life-as-Code health data.
These define the database schema and provide ORM functionality.
"""

import datetime
from typing import Any

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship

Base: Any = declarative_base()


class User(Base):
    """User accounts for multi-user support."""

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

    def __repr__(self):
        return f"<User(username={self.username})>"


class UserCredentials(Base):
    """Encrypted user credentials for external APIs."""

    __tablename__ = "user_credentials"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    garmin_email = Column(String(200))  # Store in plain text (it's just email)
    encrypted_garmin_password = Column(String(500))  # Encrypted
    encrypted_hevy_api_key = Column(String(500))  # Encrypted
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )

    # Relationships
    user = relationship("User", back_populates="credentials")

    def __repr__(self):
        return f"<UserCredentials(user_id={self.user_id}, garmin_email={self.garmin_email})>"


class UserSettings(Base):
    """User-specific settings and thresholds for personalized analysis."""

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
    """Sleep data from Garmin Connect."""

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
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="sleep_data")

    # Ensure unique constraint on user_id + date combination
    __table_args__ = (UniqueConstraint("user_id", "date", name="_user_sleep_date_uc"),)

    def __repr__(self):
        return f"<Sleep(user_id={self.user_id}, date={self.date}, total={self.total_sleep_minutes}min, score={self.sleep_score})>"


class HRV(Base):
    """Heart Rate Variability data from Garmin Connect and Apple Watch."""

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
    __table_args__ = (UniqueConstraint("user_id", "date", name="_user_hrv_date_uc"),)

    def __repr__(self):
        return f"<HRV(user_id={self.user_id}, date={self.date}, avg={self.hrv_avg}ms, status={self.hrv_status})>"


class Weight(Base):
    """Weight and body composition data from Garmin Connect."""

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

    def __repr__(self):
        return f"<Weight(user_id={self.user_id}, date={self.date}, weight={self.weight_kg}kg, bmi={self.bmi})>"


class HeartRate(Base):
    """Heart rate data from Garmin Connect."""

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
    )

    def __repr__(self):
        return f"<HeartRate(user_id={self.user_id}, date={self.date}, resting={self.resting_hr}bpm)>"


class Stress(Base):
    """Daily stress data from Garmin."""

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
    )

    # Relationships
    user = relationship("User", back_populates="stress_data")

    def __repr__(self):
        return (
            f"<Stress(user_id={self.user_id}, date={self.date}, avg={self.avg_stress})>"
        )


class Energy(Base):
    """Daily energy expenditure data from Apple Watch and Garmin."""

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
    __table_args__ = (UniqueConstraint("user_id", "date", name="_user_date_energy_uc"),)

    def __repr__(self):
        total = (self.active_energy or 0) + (self.basal_energy or 0)
        return f"<Energy(user_id={self.user_id}, date={self.date}, active={self.active_energy}kcal, basal={self.basal_energy}kcal, total={total}kcal)>"


class Steps(Base):
    """Daily steps and distance data from Garmin Connect."""

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
    __table_args__ = (UniqueConstraint("user_id", "date", name="_user_date_steps_uc"),)

    def __repr__(self):
        return f"<Steps(user_id={self.user_id}, date={self.date}, steps={self.total_steps})>"


class WorkoutSet(Base):
    """Individual workout sets from Hevy."""

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
    """Track when data was last synced from external sources."""

    __tablename__ = "data_sync"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    source = Column(String(50), nullable=False)  # 'garmin', 'hevy'
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
