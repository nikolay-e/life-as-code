"""Add CHECK constraints and missing UNIQUE constraints

Revision ID: 001_check_constraints
Revises: None
Create Date: 2024-12-17

This migration adds:
1. CHECK constraints for data validation on all health metrics tables
2. Missing UNIQUE constraints
3. The set_index column to workout_sets for deduplication
"""

from alembic import op
import sqlalchemy as sa


revision = "001_check_constraints"
down_revision = None
branch_labels = None
depends_on = None


def add_constraint_if_not_exists(constraint_sql, constraint_name, table_name):
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = '{constraint_name}'
                AND conrelid = '{table_name}'::regclass
            ) THEN
                {constraint_sql};
            END IF;
        END$$;
        """
    )


def upgrade():
    # Add set_index column to workout_sets if it doesn't exist
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'workout_sets' AND column_name = 'set_index'
            ) THEN
                ALTER TABLE workout_sets ADD COLUMN set_index INTEGER NOT NULL DEFAULT 0;
            END IF;
        END$$;
        """
    )

    # Populate set_index with sequential values per (user_id, date, exercise)
    op.execute(
        """
        WITH numbered AS (
            SELECT id, ROW_NUMBER() OVER (
                PARTITION BY user_id, date, exercise
                ORDER BY id
            ) - 1 as new_index
            FROM workout_sets
        )
        UPDATE workout_sets
        SET set_index = numbered.new_index
        FROM numbered
        WHERE workout_sets.id = numbered.id;
        """
    )

    # Sleep table CHECK constraints
    sleep_constraints = [
        ("valid_deep_minutes", "(deep_minutes >= 0) OR deep_minutes IS NULL"),
        ("valid_light_minutes", "(light_minutes >= 0) OR light_minutes IS NULL"),
        ("valid_rem_minutes", "(rem_minutes >= 0) OR rem_minutes IS NULL"),
        ("valid_awake_minutes", "(awake_minutes >= 0) OR awake_minutes IS NULL"),
        ("valid_total_sleep", "(total_sleep_minutes >= 0) OR total_sleep_minutes IS NULL"),
        ("valid_sleep_score_range", "(sleep_score >= 0 AND sleep_score <= 100) OR sleep_score IS NULL"),
        ("valid_spo2_avg_range", "(spo2_avg >= 50 AND spo2_avg <= 100) OR spo2_avg IS NULL"),
        ("valid_spo2_min_range", "(spo2_min >= 50 AND spo2_min <= 100) OR spo2_min IS NULL"),
        ("valid_respiratory_rate_range", "(respiratory_rate >= 5 AND respiratory_rate <= 50) OR respiratory_rate IS NULL"),
    ]
    for name, expr in sleep_constraints:
        add_constraint_if_not_exists(
            f"ALTER TABLE sleep ADD CONSTRAINT {name} CHECK ({expr})",
            name,
            "sleep",
        )

    # HRV table CHECK constraints
    hrv_constraints = [
        ("valid_hrv_range", "(hrv_avg >= 0 AND hrv_avg <= 500) OR hrv_avg IS NULL"),
        ("valid_baseline_low_range", "(baseline_low_ms >= 0 AND baseline_low_ms <= 500) OR baseline_low_ms IS NULL"),
        ("valid_baseline_high_range", "(baseline_high_ms >= 0 AND baseline_high_ms <= 500) OR baseline_high_ms IS NULL"),
    ]
    for name, expr in hrv_constraints:
        add_constraint_if_not_exists(
            f"ALTER TABLE hrv ADD CONSTRAINT {name} CHECK ({expr})",
            name,
            "hrv",
        )

    # Weight table CHECK constraints
    weight_constraints = [
        ("valid_weight_range", "(weight_kg > 0 AND weight_kg < 500) OR weight_kg IS NULL"),
        ("valid_bmi_range", "(bmi > 0 AND bmi < 100) OR bmi IS NULL"),
        ("valid_body_fat_range", "(body_fat_pct >= 0 AND body_fat_pct <= 100) OR body_fat_pct IS NULL"),
        ("valid_muscle_mass_range", "(muscle_mass_kg > 0 AND muscle_mass_kg < 300) OR muscle_mass_kg IS NULL"),
        ("valid_water_pct_range", "(water_pct >= 0 AND water_pct <= 100) OR water_pct IS NULL"),
    ]
    for name, expr in weight_constraints:
        add_constraint_if_not_exists(
            f"ALTER TABLE weight ADD CONSTRAINT {name} CHECK ({expr})",
            name,
            "weight",
        )

    # HeartRate table CHECK constraints
    heart_rate_constraints = [
        ("valid_resting_hr_range", "(resting_hr >= 20 AND resting_hr <= 200) OR resting_hr IS NULL"),
        ("valid_max_hr_range", "(max_hr >= 40 AND max_hr <= 250) OR max_hr IS NULL"),
        ("valid_avg_hr_range", "(avg_hr >= 30 AND avg_hr <= 220) OR avg_hr IS NULL"),
    ]
    for name, expr in heart_rate_constraints:
        add_constraint_if_not_exists(
            f"ALTER TABLE heart_rate ADD CONSTRAINT {name} CHECK ({expr})",
            name,
            "heart_rate",
        )

    # Stress table CHECK constraints
    stress_constraints = [
        ("valid_avg_stress_range", "(avg_stress >= 0 AND avg_stress <= 100) OR avg_stress IS NULL"),
        ("valid_max_stress_range", "(max_stress >= 0 AND max_stress <= 100) OR max_stress IS NULL"),
        ("valid_rest_stress_range", "(rest_stress >= 0 AND rest_stress <= 100) OR rest_stress IS NULL"),
        ("valid_activity_stress_range", "(activity_stress >= 0 AND activity_stress <= 100) OR activity_stress IS NULL"),
    ]
    for name, expr in stress_constraints:
        add_constraint_if_not_exists(
            f"ALTER TABLE stress ADD CONSTRAINT {name} CHECK ({expr})",
            name,
            "stress",
        )

    # WorkoutSet table CHECK constraints
    workout_constraints = [
        ("valid_weight_kg", "weight_kg >= 0 OR weight_kg IS NULL"),
        ("valid_reps", "reps >= 0 OR reps IS NULL"),
        ("valid_rpe_range", "(rpe >= 1 AND rpe <= 10) OR rpe IS NULL"),
        ("valid_duration", "duration_seconds >= 0 OR duration_seconds IS NULL"),
        ("valid_distance", "distance_meters >= 0 OR distance_meters IS NULL"),
    ]
    for name, expr in workout_constraints:
        add_constraint_if_not_exists(
            f"ALTER TABLE workout_sets ADD CONSTRAINT {name} CHECK ({expr})",
            name,
            "workout_sets",
        )

    # BodyBattery table CHECK constraints
    body_battery_constraints = [
        ("valid_battery_charged", "(charged >= 0 AND charged <= 100) OR charged IS NULL"),
        ("valid_battery_drained", "(drained >= 0 AND drained <= 100) OR drained IS NULL"),
        ("valid_battery_highest", "(highest >= 0 AND highest <= 100) OR highest IS NULL"),
        ("valid_battery_lowest", "(lowest >= 0 AND lowest <= 100) OR lowest IS NULL"),
    ]
    for name, expr in body_battery_constraints:
        add_constraint_if_not_exists(
            f"ALTER TABLE body_battery ADD CONSTRAINT {name} CHECK ({expr})",
            name,
            "body_battery",
        )

    # WhoopRecovery table CHECK constraints
    whoop_recovery_constraints = [
        ("valid_recovery_score_range", "(recovery_score >= 0 AND recovery_score <= 100) OR recovery_score IS NULL"),
        ("valid_whoop_resting_hr_range", "(resting_heart_rate >= 20 AND resting_heart_rate <= 200) OR resting_heart_rate IS NULL"),
        ("valid_hrv_rmssd_range", "(hrv_rmssd >= 0 AND hrv_rmssd <= 500) OR hrv_rmssd IS NULL"),
        ("valid_whoop_spo2_range", "(spo2_percentage >= 50 AND spo2_percentage <= 100) OR spo2_percentage IS NULL"),
    ]
    for name, expr in whoop_recovery_constraints:
        add_constraint_if_not_exists(
            f"ALTER TABLE whoop_recovery ADD CONSTRAINT {name} CHECK ({expr})",
            name,
            "whoop_recovery",
        )

    # WhoopSleep table CHECK constraints
    whoop_sleep_constraints = [
        ("valid_sleep_performance_range", "(sleep_performance_percentage >= 0 AND sleep_performance_percentage <= 100) OR sleep_performance_percentage IS NULL"),
        ("valid_sleep_consistency_range", "(sleep_consistency_percentage >= 0 AND sleep_consistency_percentage <= 100) OR sleep_consistency_percentage IS NULL"),
        ("valid_sleep_efficiency_range", "(sleep_efficiency_percentage >= 0 AND sleep_efficiency_percentage <= 100) OR sleep_efficiency_percentage IS NULL"),
        ("valid_whoop_total_sleep", "(total_sleep_duration_minutes >= 0) OR total_sleep_duration_minutes IS NULL"),
        ("valid_whoop_respiratory_rate", "(respiratory_rate >= 5 AND respiratory_rate <= 50) OR respiratory_rate IS NULL"),
    ]
    for name, expr in whoop_sleep_constraints:
        add_constraint_if_not_exists(
            f"ALTER TABLE whoop_sleep ADD CONSTRAINT {name} CHECK ({expr})",
            name,
            "whoop_sleep",
        )

    # WhoopWorkout table CHECK constraints
    whoop_workout_constraints = [
        ("valid_strain_range", "(strain >= 0 AND strain <= 21) OR strain IS NULL"),
        ("valid_whoop_workout_avg_hr", "(avg_heart_rate >= 30 AND avg_heart_rate <= 250) OR avg_heart_rate IS NULL"),
        ("valid_whoop_workout_max_hr", "(max_heart_rate >= 40 AND max_heart_rate <= 250) OR max_heart_rate IS NULL"),
        ("valid_kilojoules", "(kilojoules >= 0) OR kilojoules IS NULL"),
        ("valid_whoop_distance", "(distance_meters >= 0) OR distance_meters IS NULL"),
    ]
    for name, expr in whoop_workout_constraints:
        add_constraint_if_not_exists(
            f"ALTER TABLE whoop_workouts ADD CONSTRAINT {name} CHECK ({expr})",
            name,
            "whoop_workouts",
        )

    # Add new UNIQUE constraint for workout_sets with set_index
    # First drop the old constraint if it exists, then add the new one
    op.execute(
        """
        DO $$
        BEGIN
            -- Drop old constraint if exists
            IF EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = '_user_workout_set_uc'
                AND conrelid = 'workout_sets'::regclass
            ) THEN
                ALTER TABLE workout_sets DROP CONSTRAINT _user_workout_set_uc;
            END IF;

            -- Add new constraint with set_index
            ALTER TABLE workout_sets
            ADD CONSTRAINT _user_workout_set_uc
            UNIQUE (user_id, date, exercise, set_index);
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END$$;
        """
    )

    # Add UNIQUE constraint for data_sync
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = '_user_source_datatype_uc'
            ) THEN
                ALTER TABLE data_sync
                ADD CONSTRAINT _user_source_datatype_uc
                UNIQUE (user_id, source, data_type);
            END IF;
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END$$;
        """
    )

    # Add UNIQUE constraint for whoop_workouts
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = '_user_whoop_workout_uc'
            ) THEN
                ALTER TABLE whoop_workouts
                ADD CONSTRAINT _user_whoop_workout_uc
                UNIQUE (user_id, date, start_time);
            END IF;
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END$$;
        """
    )


def downgrade():
    # Remove CHECK constraints from all tables
    tables_constraints = {
        "sleep": [
            "valid_deep_minutes", "valid_light_minutes", "valid_rem_minutes",
            "valid_awake_minutes", "valid_total_sleep", "valid_sleep_score_range",
            "valid_spo2_avg_range", "valid_spo2_min_range", "valid_respiratory_rate_range",
        ],
        "hrv": ["valid_hrv_range", "valid_baseline_low_range", "valid_baseline_high_range"],
        "weight": [
            "valid_weight_range", "valid_bmi_range", "valid_body_fat_range",
            "valid_muscle_mass_range", "valid_water_pct_range",
        ],
        "heart_rate": ["valid_resting_hr_range", "valid_max_hr_range", "valid_avg_hr_range"],
        "stress": [
            "valid_avg_stress_range", "valid_max_stress_range",
            "valid_rest_stress_range", "valid_activity_stress_range",
        ],
        "workout_sets": [
            "valid_weight_kg", "valid_reps", "valid_rpe_range",
            "valid_duration", "valid_distance",
        ],
        "body_battery": [
            "valid_battery_charged", "valid_battery_drained",
            "valid_battery_highest", "valid_battery_lowest",
        ],
        "whoop_recovery": [
            "valid_recovery_score_range", "valid_whoop_resting_hr_range",
            "valid_hrv_rmssd_range", "valid_whoop_spo2_range",
        ],
        "whoop_sleep": [
            "valid_sleep_performance_range", "valid_sleep_consistency_range",
            "valid_sleep_efficiency_range", "valid_whoop_total_sleep",
            "valid_whoop_respiratory_rate",
        ],
        "whoop_workouts": [
            "valid_strain_range", "valid_whoop_workout_avg_hr",
            "valid_whoop_workout_max_hr", "valid_kilojoules", "valid_whoop_distance",
        ],
    }

    for table, constraints in tables_constraints.items():
        for constraint in constraints:
            op.execute(
                f"""
                DO $$
                BEGIN
                    ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {constraint};
                EXCEPTION
                    WHEN undefined_object THEN NULL;
                END$$;
                """
            )

    # Remove UNIQUE constraints
    op.execute(
        """
        DO $$
        BEGIN
            ALTER TABLE data_sync DROP CONSTRAINT IF EXISTS _user_source_datatype_uc;
            ALTER TABLE whoop_workouts DROP CONSTRAINT IF EXISTS _user_whoop_workout_uc;
        EXCEPTION
            WHEN undefined_object THEN NULL;
        END$$;
        """
    )

    # Remove set_index column from workout_sets
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'workout_sets' AND column_name = 'set_index'
            ) THEN
                ALTER TABLE workout_sets DROP COLUMN set_index;
            END IF;
        END$$;
        """
    )
