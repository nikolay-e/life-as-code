"""Add updated_at column to all health data tables

Revision ID: 019_add_updated_at
Revises: 018_add_longevity_tables
Create Date: 2026-03-21
"""

from alembic import op
import sqlalchemy as sa

revision = "019_add_updated_at"
down_revision = "018_add_longevity_tables"
branch_labels = None
depends_on = None

TABLES = [
    "sleep",
    "hrv",
    "weight",
    "heart_rate",
    "stress",
    "energy",
    "steps",
    "workout_sets",
    "whoop_recovery",
    "whoop_sleep",
    "whoop_workouts",
    "whoop_cycles",
    "garmin_training_status",
    "garmin_activities",
    "garmin_race_predictions",
]


def upgrade() -> None:
    for table in TABLES:
        op.add_column(
            table,
            sa.Column(
                "updated_at",
                sa.DateTime(),
                server_default=sa.func.now(),
                nullable=True,
            ),
        )


def downgrade() -> None:
    for table in TABLES:
        op.drop_column(table, "updated_at")
