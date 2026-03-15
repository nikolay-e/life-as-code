"""
Data loading utilities for Life-as-Code application.
Handles database queries and data preprocessing for visualizations.
"""

import pandas as pd
from sqlalchemy import select

from models import (
    HRV,
    Energy,
    GarminActivity,
    GarminRacePrediction,
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
    from database import read_engine

    data = {}

    models_map = [
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
        (GarminActivity, "garmin_activity"),
        (GarminRacePrediction, "garmin_race_prediction"),
    ]

    with read_engine.connect() as conn:
        for model, key in models_map:
            query = select(model).where(
                model.user_id == user_id, model.date.between(start_date, end_date)
            )
            df = pd.read_sql(query, conn)
            data[key] = df if not df.empty else pd.DataFrame()

    return data


def get_workout_volume_data(workouts_df):
    if workouts_df.empty:
        return pd.DataFrame()

    workouts_df.loc[:, "volume"] = workouts_df["weight_kg"].fillna(0) * workouts_df[
        "reps"
    ].fillna(0)

    daily_volume = (
        workouts_df.groupby("date")
        .agg({"volume": "sum", "exercise": "count"})
        .reset_index()
    )

    daily_volume.columns = ["date", "total_volume", "total_sets"]
    return daily_volume


def get_detailed_workout_data(start_date, end_date, user_id):
    from sqlalchemy import text

    from database import read_engine

    query = text(
        """
        SELECT
            date::text,
            exercise,
            json_agg(
                json_build_object(
                    'set_index', set_index,
                    'weight_kg', weight_kg,
                    'reps', reps,
                    'rpe', rpe,
                    'set_type', set_type
                ) ORDER BY set_index
            ) as sets,
            COALESCE(SUM(COALESCE(weight_kg, 0) * COALESCE(reps, 0)), 0)::float as total_volume,
            COUNT(*)::int as total_sets,
            AVG(rpe) FILTER (WHERE rpe IS NOT NULL) as avg_rpe
        FROM workout_sets
        WHERE user_id = :user_id
          AND date BETWEEN :start_date AND :end_date
        GROUP BY date, exercise
        ORDER BY date DESC, exercise ASC
    """
    )

    with read_engine.connect() as conn:
        result = conn.execute(
            query,
            {"user_id": user_id, "start_date": start_date, "end_date": end_date},
        )
        return [dict(row._mapping) for row in result]


def _int_or_none(row, col):
    return int(row[col]) if pd.notna(row[col]) else None


def _float_or_none(row, col):
    return float(row[col]) if pd.notna(row[col]) else None


def _row_to_garmin_activity(row) -> dict:
    return {
        "activity_id": row["activity_id"],
        "date": str(row["date"]),
        "start_time": (
            row["start_time"].isoformat() if pd.notna(row["start_time"]) else None
        ),
        "activity_type": row["activity_type"],
        "activity_name": row["activity_name"],
        "duration_seconds": _int_or_none(row, "duration_seconds"),
        "distance_meters": _float_or_none(row, "distance_meters"),
        "avg_heart_rate": _int_or_none(row, "avg_heart_rate"),
        "max_heart_rate": _int_or_none(row, "max_heart_rate"),
        "calories": _int_or_none(row, "calories"),
        "avg_speed_mps": _float_or_none(row, "avg_speed_mps"),
        "max_speed_mps": _float_or_none(row, "max_speed_mps"),
        "elevation_gain_meters": _float_or_none(row, "elevation_gain_meters"),
        "elevation_loss_meters": _float_or_none(row, "elevation_loss_meters"),
        "avg_power_watts": _float_or_none(row, "avg_power_watts"),
        "max_power_watts": _float_or_none(row, "max_power_watts"),
        "training_effect_aerobic": _float_or_none(row, "training_effect_aerobic"),
        "training_effect_anaerobic": _float_or_none(row, "training_effect_anaerobic"),
        "vo2_max_value": _float_or_none(row, "vo2_max_value"),
        "hr_zone_one_seconds": _int_or_none(row, "hr_zone_one_seconds"),
        "hr_zone_two_seconds": _int_or_none(row, "hr_zone_two_seconds"),
        "hr_zone_three_seconds": _int_or_none(row, "hr_zone_three_seconds"),
        "hr_zone_four_seconds": _int_or_none(row, "hr_zone_four_seconds"),
        "hr_zone_five_seconds": _int_or_none(row, "hr_zone_five_seconds"),
    }


def get_garmin_activities_data(start_date, end_date, user_id):
    from database import read_engine

    query = select(GarminActivity).where(
        GarminActivity.user_id == user_id,
        GarminActivity.date.between(start_date, end_date),
    )

    with read_engine.connect() as conn:
        df = pd.read_sql(query, conn)

    if df.empty:
        return []

    result = [_row_to_garmin_activity(row) for _, row in df.iterrows()]
    result.sort(key=lambda x: x["start_time"] or x["date"], reverse=True)
    return result
