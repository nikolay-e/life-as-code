"""Add Google as valid data source

Revision ID: 006_add_google_source
Revises: 005_fix_constraints
Create Date: 2024-12-20

This migration adds 'google' as a valid source in the CHECK constraints
for data_sync and sync_progress tables to support Google Fit data import.
"""

from alembic import op


revision = "006_add_google_source"
down_revision = "005_fix_constraints"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        DO $$
        BEGIN
            ALTER TABLE data_sync DROP CONSTRAINT IF EXISTS valid_sync_source;
        EXCEPTION
            WHEN undefined_object THEN NULL;
        END$$;
        """
    )

    op.execute(
        """
        ALTER TABLE data_sync
        ADD CONSTRAINT valid_sync_source CHECK (source IN ('garmin', 'hevy', 'whoop', 'google'));
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            ALTER TABLE sync_progress DROP CONSTRAINT IF EXISTS valid_sync_progress_source;
        EXCEPTION
            WHEN undefined_object THEN NULL;
        END$$;
        """
    )

    op.execute(
        """
        ALTER TABLE sync_progress
        ADD CONSTRAINT valid_sync_progress_source CHECK (source IN ('garmin', 'hevy', 'whoop', 'google'));
        """
    )


def downgrade():
    op.execute(
        """
        DO $$
        BEGIN
            ALTER TABLE data_sync DROP CONSTRAINT IF EXISTS valid_sync_source;
        EXCEPTION
            WHEN undefined_object THEN NULL;
        END$$;
        """
    )

    op.execute(
        """
        ALTER TABLE data_sync
        ADD CONSTRAINT valid_sync_source CHECK (source IN ('garmin', 'hevy', 'whoop'));
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            ALTER TABLE sync_progress DROP CONSTRAINT IF EXISTS valid_sync_progress_source;
        EXCEPTION
            WHEN undefined_object THEN NULL;
        END$$;
        """
    )

    op.execute(
        """
        ALTER TABLE sync_progress
        ADD CONSTRAINT valid_sync_progress_source CHECK (source IN ('garmin', 'hevy', 'whoop'));
        """
    )
