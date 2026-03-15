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

    result = []
    for _, row in df.iterrows():
        activity = {
            "activity_id": row["activity_id"],
            "date": str(row["date"]),
            "start_time": (
                row["start_time"].isoformat() if pd.notna(row["start_time"]) else None
            ),
            "activity_type": row["activity_type"],
            "activity_name": row["activity_name"],
            "duration_seconds": (
                int(row["duration_seconds"])
                if pd.notna(row["duration_seconds"])
                else None
            ),
            "distance_meters": (
                float(row["distance_meters"])
                if pd.notna(row["distance_meters"])
                else None
            ),
            "avg_heart_rate": (
                int(row["avg_heart_rate"]) if pd.notna(row["avg_heart_rate"]) else None
            ),
            "max_heart_rate": (
                int(row["max_heart_rate"]) if pd.notna(row["max_heart_rate"]) else None
            ),
            "calories": int(row["calories"]) if pd.notna(row["calories"]) else None,
            "avg_speed_mps": (
                float(row["avg_speed_mps"]) if pd.notna(row["avg_speed_mps"]) else None
            ),
            "max_speed_mps": (
                float(row["max_speed_mps"]) if pd.notna(row["max_speed_mps"]) else None
            ),
            "elevation_gain_meters": (
                float(row["elevation_gain_meters"])
                if pd.notna(row["elevation_gain_meters"])
                else None
            ),
            "elevation_loss_meters": (
                float(row["elevation_loss_meters"])
                if pd.notna(row["elevation_loss_meters"])
                else None
            ),
            "avg_power_watts": (
                float(row["avg_power_watts"])
                if pd.notna(row["avg_power_watts"])
                else None
            ),
            "max_power_watts": (
                float(row["max_power_watts"])
                if pd.notna(row["max_power_watts"])
                else None
            ),
            "training_effect_aerobic": (
                float(row["training_effect_aerobic"])
                if pd.notna(row["training_effect_aerobic"])
                else None
            ),
            "training_effect_anaerobic": (
                float(row["training_effect_anaerobic"])
                if pd.notna(row["training_effect_anaerobic"])
                else None
            ),
            "vo2_max_value": (
                float(row["vo2_max_value"]) if pd.notna(row["vo2_max_value"]) else None
            ),
            "hr_zone_one_seconds": (
                int(row["hr_zone_one_seconds"])
                if pd.notna(row["hr_zone_one_seconds"])
                else None
            ),
            "hr_zone_two_seconds": (
                int(row["hr_zone_two_seconds"])
                if pd.notna(row["hr_zone_two_seconds"])
                else None
            ),
            "hr_zone_three_seconds": (
                int(row["hr_zone_three_seconds"])
                if pd.notna(row["hr_zone_three_seconds"])
                else None
            ),
            "hr_zone_four_seconds": (
                int(row["hr_zone_four_seconds"])
                if pd.notna(row["hr_zone_four_seconds"])
                else None
            ),
            "hr_zone_five_seconds": (
                int(row["hr_zone_five_seconds"])
                if pd.notna(row["hr_zone_five_seconds"])
                else None
            ),
        }
        result.append(activity)

    result.sort(key=lambda x: x["start_time"] or x["date"], reverse=True)
    return result
