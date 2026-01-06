"""
Data loading utilities for Life-as-Code application.
Handles database queries and data preprocessing for visualizations.
"""

import pandas as pd
from sqlalchemy import select

from models import (
    HRV,
    Energy,
    GarminTrainingStatus,
    HeartRate,
    Sleep,
    Steps,
    Stress,
    Weight,
    WhoopCycle,
    WhoopRecovery,
    WhoopSleep,
    WhoopWorkout,
    WorkoutSet,
)


def load_data_for_user(start_date, end_date, user_id):
    """Load data from database for the specified user and date range."""
    from database import get_db_session_context

    data = {}

    # Use context manager for better session handling
    with get_db_session_context() as db:
        # Load each data type filtered by user_id
        for model, key in [
            (Sleep, "sleep"),
            (HRV, "hrv"),
            (Weight, "weight"),
            (HeartRate, "heart_rate"),
            (Stress, "stress"),
            (Steps, "steps"),
            (Energy, "energy"),
            (WorkoutSet, "workouts"),
            (WhoopRecovery, "whoop_recovery"),
            (WhoopSleep, "whoop_sleep"),
            (WhoopWorkout, "whoop_workout"),
            (WhoopCycle, "whoop_cycle"),
            (GarminTrainingStatus, "garmin_training_status"),
        ]:
            query = select(model).where(
                model.user_id == user_id, model.date.between(start_date, end_date)
            )
            df = pd.read_sql(query, db.connection())
            data[key] = df if not df.empty else pd.DataFrame()

    return data


def get_workout_volume_data(workouts_df):
    """Calculate workout volume metrics from workout data."""
    if workouts_df.empty:
        return pd.DataFrame()

    # Calculate daily workout volume (weight * reps)
    # Use .loc to avoid copy - original df is not modified after this function
    workouts_df.loc[:, "volume"] = workouts_df["weight_kg"].fillna(0) * workouts_df[
        "reps"
    ].fillna(0)

    daily_volume = (
        workouts_df.groupby("date")
        .agg({"volume": "sum", "exercise": "count"})  # Number of sets
        .reset_index()
    )

    daily_volume.columns = ["date", "total_volume", "total_sets"]
    return daily_volume
