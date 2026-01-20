"""Add source column to stress table

Revision ID: 013_add_source_to_stress
Revises: 012_add_training_readiness
Create Date: 2025-01-20

Adds source column to stress table to track data origin (garmin, google, apple_health, hevy, whoop).
Updates unique constraint to allow same date from different sources.
"""

from alembic import op
import sqlalchemy as sa


revision = "013_add_source_to_stress"
down_revision = "012_add_training_readiness"
branch_labels = None
depends_on = None

VALID_SOURCES = "('garmin', 'google', 'apple_health', 'hevy', 'whoop')"


def upgrade():
    op.add_column(
        "stress",
        sa.Column("source", sa.String(50), nullable=True),
    )

    op.execute("UPDATE stress SET source = 'garmin' WHERE source IS NULL")

    op.alter_column("stress", "source", nullable=False)

    op.execute(
        f"""
        ALTER TABLE stress
        ADD CONSTRAINT valid_stress_source CHECK (source IN {VALID_SOURCES});
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            ALTER TABLE stress DROP CONSTRAINT IF EXISTS _user_stress_date_uc;
        EXCEPTION WHEN undefined_object THEN NULL;
        END$$;
        """
    )
    op.create_unique_constraint(
        "_user_stress_date_source_uc", "stress", ["user_id", "date", "source"]
    )


def downgrade():
    op.execute(
        """
        DO $$
        BEGIN
            ALTER TABLE stress DROP CONSTRAINT IF EXISTS valid_stress_source;
        EXCEPTION WHEN undefined_object THEN NULL;
        END$$;
        """
    )

    op.drop_constraint("_user_stress_date_source_uc", "stress", type_="unique")
    op.create_unique_constraint("_user_stress_date_uc", "stress", ["user_id", "date"])

    op.drop_column("stress", "source")
