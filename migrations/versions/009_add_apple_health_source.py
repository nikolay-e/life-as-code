"""Add Apple Health as valid data source

Revision ID: 009_add_apple_health_source
Revises: 008_remove_webauthn
Create Date: 2025-01-01

This migration adds 'apple_health' as a valid source in the CHECK constraints
for data_sync and sync_progress tables to support Apple Health data import.
"""

from alembic import op


revision = "009_add_apple_health_source"
down_revision = "008_remove_webauthn"
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
        ADD CONSTRAINT valid_sync_source CHECK (source IN ('garmin', 'hevy', 'whoop', 'google', 'apple_health'));
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
        ADD CONSTRAINT valid_sync_progress_source CHECK (source IN ('garmin', 'hevy', 'whoop', 'google', 'apple_health'));
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
