"""Add sync_progress table for progressive sync tracking

Revision ID: 004_sync_progress
Revises: 003_rm_apple_health
Create Date: 2024-12-20
"""

import sqlalchemy as sa
from alembic import op

revision = "004_sync_progress"
down_revision = "003_rm_apple_health"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "sync_progress",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("oldest_synced_date", sa.Date(), nullable=True),
        sa.Column("newest_synced_date", sa.Date(), nullable=True),
        sa.Column("current_window", sa.String(20), server_default="day"),
        sa.Column("window_status", sa.String(20), server_default="pending"),
        sa.Column("day_completed", sa.Date(), nullable=True),
        sa.Column("week_completed", sa.Date(), nullable=True),
        sa.Column("month_completed", sa.Date(), nullable=True),
        sa.Column("year_completed", sa.Date(), nullable=True),
        sa.Column("full_sync_completed", sa.Date(), nullable=True),
        sa.Column("last_sync_started_at", sa.DateTime(), nullable=True),
        sa.Column("last_sync_completed_at", sa.DateTime(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=True
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("ix_sync_progress_user_id", "sync_progress", ["user_id"])
    op.create_index(
        "idx_sync_progress_user_source", "sync_progress", ["user_id", "source"]
    )
    op.create_unique_constraint(
        "_user_sync_progress_source_uc", "sync_progress", ["user_id", "source"]
    )

    op.execute(
        """
        ALTER TABLE sync_progress
        ADD CONSTRAINT valid_sync_progress_source
        CHECK (source IN ('garmin', 'hevy', 'whoop'))
        """
    )

    op.execute(
        """
        ALTER TABLE sync_progress
        ADD CONSTRAINT valid_current_window
        CHECK (current_window IN ('day', 'week', 'month', 'year', 'all'))
        """
    )

    op.execute(
        """
        ALTER TABLE sync_progress
        ADD CONSTRAINT valid_window_status
        CHECK (window_status IN ('pending', 'in_progress', 'completed', 'failed'))
        """
    )


def downgrade():
    op.drop_constraint("valid_window_status", "sync_progress", type_="check")
    op.drop_constraint("valid_current_window", "sync_progress", type_="check")
    op.drop_constraint("valid_sync_progress_source", "sync_progress", type_="check")
    op.drop_constraint("_user_sync_progress_source_uc", "sync_progress", type_="unique")
    op.drop_index("idx_sync_progress_user_source", table_name="sync_progress")
    op.drop_index("ix_sync_progress_user_id", table_name="sync_progress")
    op.drop_table("sync_progress")
