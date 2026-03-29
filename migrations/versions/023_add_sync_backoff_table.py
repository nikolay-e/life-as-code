"""Add sync_backoff table for persistent rate limit tracking

Revision ID: 023_sync_backoff
Revises: 022_fix_calibrating
Create Date: 2026-03-29
"""

import sqlalchemy as sa
from alembic import op

revision = "023_sync_backoff"
down_revision = "022_fix_calibrating"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sync_backoff",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("backoff_level", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "last_failure_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "is_rate_limited",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.UniqueConstraint("user_id", "source", name="_sync_backoff_user_source_uc"),
    )
    op.create_index(
        "idx_sync_backoff_user_source", "sync_backoff", ["user_id", "source"]
    )


def downgrade() -> None:
    op.drop_index("idx_sync_backoff_user_source")
    op.drop_table("sync_backoff")
