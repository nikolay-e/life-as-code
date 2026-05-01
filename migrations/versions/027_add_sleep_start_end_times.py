"""Add sleep_start_time / sleep_end_time to sleep, whoop_sleep, eight_sleep_sessions

Revision ID: 027_sleep_start_end_times
Revises: 026_sleep_skin_temp_deviation
Create Date: 2026-05-01

Sleep providers (Garmin, Whoop, Eight Sleep) all return sleep onset / wake-up
timestamps but until now we discarded them and kept only durations + the calendar
date. Without bedtime we can't analyse sleep onset, wake time, social jet lag,
sleep midpoint or correlate timing with HRV / recovery the next day.

Stored as TIMESTAMPTZ (UTC moment). Local hour can be derived downstream from
the user's timezone; storing the absolute moment keeps arithmetic consistent
across DST transitions and travel.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "027_sleep_start_end_times"
down_revision: str | None = "026_sleep_skin_temp_deviation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_TABLES = ("sleep", "whoop_sleep", "eight_sleep_sessions")


def upgrade() -> None:
    for table in _TABLES:
        op.add_column(
            table,
            sa.Column("sleep_start_time", sa.DateTime(timezone=True), nullable=True),
        )
        op.add_column(
            table,
            sa.Column("sleep_end_time", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_check_constraint(
            f"valid_{table}_sleep_window",
            table,
            "sleep_end_time IS NULL "
            "OR sleep_start_time IS NULL "
            "OR sleep_end_time > sleep_start_time",
        )


def downgrade() -> None:
    for table in _TABLES:
        op.drop_constraint(f"valid_{table}_sleep_window", table, type_="check")
        op.drop_column(table, "sleep_end_time")
        op.drop_column(table, "sleep_start_time")
