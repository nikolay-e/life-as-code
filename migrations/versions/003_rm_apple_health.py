"""Remove apple_health from valid sync sources

Revision ID: 003_rm_apple_health
Revises: 002_garmin_whoop
Create Date: 2024-12-18
"""

from alembic import op

revision = "003_rm_apple_health"
down_revision = "002_garmin_whoop"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'valid_sync_source'
                AND conrelid = 'data_sync'::regclass
            ) THEN
                ALTER TABLE data_sync DROP CONSTRAINT valid_sync_source;
            END IF;

            ALTER TABLE data_sync
            ADD CONSTRAINT valid_sync_source
            CHECK (source IN ('garmin', 'hevy', 'whoop'));
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END$$;
        """
    )


def downgrade():
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'valid_sync_source'
                AND conrelid = 'data_sync'::regclass
            ) THEN
                ALTER TABLE data_sync DROP CONSTRAINT valid_sync_source;
            END IF;

            ALTER TABLE data_sync
            ADD CONSTRAINT valid_sync_source
            CHECK (source IN ('garmin', 'hevy', 'whoop', 'apple_health'));
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END$$;
        """
    )
