"""Fix CHECK constraints to allow valid data

Revision ID: 005_fix_constraints
Revises: 004_sync_progress
Create Date: 2024-12-20

This migration fixes constraints that may have been created with
incorrect expressions, ensuring reps=0 is allowed.
"""

from alembic import op

revision = "005_fix_constraints"
down_revision = "004_sync_progress"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        DO $$
        BEGIN
            ALTER TABLE workout_sets DROP CONSTRAINT IF EXISTS valid_reps;
        EXCEPTION
            WHEN undefined_object THEN NULL;
        END$$;
        """
    )

    op.execute(
        """
        ALTER TABLE workout_sets
        ADD CONSTRAINT valid_reps CHECK (reps >= 0 OR reps IS NULL);
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            ALTER TABLE workout_sets DROP CONSTRAINT IF EXISTS valid_weight_kg;
        EXCEPTION
            WHEN undefined_object THEN NULL;
        END$$;
        """
    )

    op.execute(
        """
        ALTER TABLE workout_sets
        ADD CONSTRAINT valid_weight_kg CHECK (weight_kg >= 0 OR weight_kg IS NULL);
        """
    )


def downgrade():
    op.execute("ALTER TABLE workout_sets DROP CONSTRAINT IF EXISTS valid_reps")
    op.execute("ALTER TABLE workout_sets DROP CONSTRAINT IF EXISTS valid_weight_kg")
