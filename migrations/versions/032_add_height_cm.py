"""Add height_cm to user_settings

Revision ID: 032_add_height_cm
Revises: 031_backfill_health_log
Create Date: 2026-05-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "032_add_height_cm"
down_revision: str | None = "031_backfill_health_log"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user_settings",
        sa.Column("height_cm", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_settings", "height_cm")
