"""Sleep table: drop dead sleep_quality_score / sleep_recovery_score, add skin_temp_deviation_c

Revision ID: 026_sleep_skin_temp_deviation
Revises: 025_bot_messages
Create Date: 2026-05-01

The Sleep table had `sleep_quality_score` and `sleep_recovery_score` columns intended
for Eight Sleep / Whoop quality metrics, but those providers write to their own tables
(`eight_sleep_sessions`, `whoop_sleep`) — these columns on `sleep` were never populated.

`skin_temp_deviation_c` replaces the misnamed `skin_temp_celsius` mapping for Garmin's
`avgSkinTempDeviationC` field which is a deviation (e.g. -0.5, +0.3), not absolute temp.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "026_sleep_skin_temp_deviation"
down_revision: str | None = "025_bot_messages"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("sleep", "sleep_quality_score")
    op.drop_column("sleep", "sleep_recovery_score")

    op.add_column(
        "sleep",
        sa.Column("skin_temp_deviation_c", sa.Float(), nullable=True),
    )
    op.create_check_constraint(
        "valid_skin_temp_deviation_range",
        "sleep",
        "(skin_temp_deviation_c >= -10 AND skin_temp_deviation_c <= 10) "
        "OR skin_temp_deviation_c IS NULL",
    )


def downgrade() -> None:
    op.drop_constraint("valid_skin_temp_deviation_range", "sleep", type_="check")
    op.drop_column("sleep", "skin_temp_deviation_c")

    op.add_column("sleep", sa.Column("sleep_quality_score", sa.Float(), nullable=True))
    op.add_column("sleep", sa.Column("sleep_recovery_score", sa.Float(), nullable=True))
