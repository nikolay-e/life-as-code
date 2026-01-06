"""Add source column to data tables

Revision ID: 010_add_source_to_data_tables
Revises: 009_add_apple_health_source
Create Date: 2025-01-06

Adds source column to sleep, hrv, energy, heart_rate, steps, weight tables
to track data origin (garmin, google, apple_health, hevy, whoop).
Updates unique constraints to allow same date from different sources.
"""

from alembic import op
import sqlalchemy as sa


revision = "010_add_source_to_data_tables"
down_revision = "009_add_apple_health_source"
branch_labels = None
depends_on = None

TABLES = ["sleep", "steps", "energy", "hrv", "heart_rate", "weight"]
VALID_SOURCES = "('garmin', 'google', 'apple_health', 'hevy', 'whoop')"


def upgrade():
    for table in TABLES:
        op.add_column(
            table,
            sa.Column("source", sa.String(50), nullable=True),
        )

        op.execute(f"UPDATE {table} SET source = 'garmin' WHERE source IS NULL")

        op.alter_column(table, "source", nullable=False)

        op.execute(
            f"""
            ALTER TABLE {table}
            ADD CONSTRAINT valid_{table}_source CHECK (source IN {VALID_SOURCES});
            """
        )

    op.execute(
        """
        DO $$
        BEGIN
            ALTER TABLE sleep DROP CONSTRAINT IF EXISTS _user_sleep_date_uc;
        EXCEPTION WHEN undefined_object THEN NULL;
        END$$;
        """
    )
    op.create_unique_constraint(
        "_user_sleep_date_source_uc", "sleep", ["user_id", "date", "source"]
    )

    op.execute(
        """
        DO $$
        BEGIN
            ALTER TABLE steps DROP CONSTRAINT IF EXISTS _user_date_steps_uc;
        EXCEPTION WHEN undefined_object THEN NULL;
        END$$;
        """
    )
    op.create_unique_constraint(
        "_user_steps_date_source_uc", "steps", ["user_id", "date", "source"]
    )

    op.execute(
        """
        DO $$
        BEGIN
            ALTER TABLE energy DROP CONSTRAINT IF EXISTS _user_date_energy_uc;
        EXCEPTION WHEN undefined_object THEN NULL;
        END$$;
        """
    )
    op.create_unique_constraint(
        "_user_energy_date_source_uc", "energy", ["user_id", "date", "source"]
    )

    op.execute(
        """
        DO $$
        BEGIN
            ALTER TABLE hrv DROP CONSTRAINT IF EXISTS _user_hrv_date_uc;
        EXCEPTION WHEN undefined_object THEN NULL;
        END$$;
        """
    )
    op.create_unique_constraint(
        "_user_hrv_date_source_uc", "hrv", ["user_id", "date", "source"]
    )

    op.execute(
        """
        DO $$
        BEGIN
            ALTER TABLE heart_rate DROP CONSTRAINT IF EXISTS _user_date_heart_rate_uc;
        EXCEPTION WHEN undefined_object THEN NULL;
        END$$;
        """
    )
    op.create_unique_constraint(
        "_user_heart_rate_date_source_uc", "heart_rate", ["user_id", "date", "source"]
    )

    op.execute(
        """
        DO $$
        BEGIN
            ALTER TABLE weight DROP CONSTRAINT IF EXISTS _user_date_weight_uc;
        EXCEPTION WHEN undefined_object THEN NULL;
        END$$;
        """
    )
    op.create_unique_constraint(
        "_user_weight_date_source_uc", "weight", ["user_id", "date", "source"]
    )


def downgrade():
    for table in TABLES:
        op.execute(
            f"""
            DO $$
            BEGIN
                ALTER TABLE {table} DROP CONSTRAINT IF EXISTS valid_{table}_source;
            EXCEPTION WHEN undefined_object THEN NULL;
            END$$;
            """
        )

    op.drop_constraint("_user_sleep_date_source_uc", "sleep", type_="unique")
    op.create_unique_constraint("_user_sleep_date_uc", "sleep", ["user_id", "date"])

    op.drop_constraint("_user_steps_date_source_uc", "steps", type_="unique")
    op.create_unique_constraint("_user_date_steps_uc", "steps", ["user_id", "date"])

    op.drop_constraint("_user_energy_date_source_uc", "energy", type_="unique")
    op.create_unique_constraint("_user_date_energy_uc", "energy", ["user_id", "date"])

    op.drop_constraint("_user_hrv_date_source_uc", "hrv", type_="unique")
    op.create_unique_constraint("_user_hrv_date_uc", "hrv", ["user_id", "date"])

    op.drop_constraint("_user_heart_rate_date_source_uc", "heart_rate", type_="unique")
    op.create_unique_constraint(
        "_user_date_heart_rate_uc", "heart_rate", ["user_id", "date"]
    )

    op.drop_constraint("_user_weight_date_source_uc", "weight", type_="unique")
    op.create_unique_constraint("_user_date_weight_uc", "weight", ["user_id", "date"])

    for table in TABLES:
        op.drop_column(table, "source")
