"""Add missing WHOOP API v2 fields to sleep and workout tables

Revision ID: 016_add_whoop_fields
Revises: 015_add_snapshots_alerts
Create Date: 2026-02-21

Sleep: sleep_need breakdown (4), sleep_cycle_count, disturbance_count, no_data_minutes
Workouts: end_time, percent_recorded, altitude_change, 6 HR zone duration columns
"""

from alembic import op
import sqlalchemy as sa

revision = "016_add_whoop_fields"
down_revision = "015_add_snapshots_alerts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("whoop_sleep", sa.Column("sleep_need_baseline_minutes", sa.Integer()))
    op.add_column("whoop_sleep", sa.Column("sleep_need_debt_minutes", sa.Integer()))
    op.add_column("whoop_sleep", sa.Column("sleep_need_strain_minutes", sa.Integer()))
    op.add_column("whoop_sleep", sa.Column("sleep_need_nap_minutes", sa.Integer()))
    op.add_column("whoop_sleep", sa.Column("sleep_cycle_count", sa.Integer()))
    op.add_column("whoop_sleep", sa.Column("disturbance_count", sa.Integer()))
    op.add_column("whoop_sleep", sa.Column("no_data_minutes", sa.Integer()))

    op.add_column("whoop_workouts", sa.Column("end_time", sa.DateTime()))
    op.add_column("whoop_workouts", sa.Column("percent_recorded", sa.Float()))
    op.add_column("whoop_workouts", sa.Column("altitude_change_meters", sa.Float()))
    op.add_column("whoop_workouts", sa.Column("zone_zero_millis", sa.Integer()))
    op.add_column("whoop_workouts", sa.Column("zone_one_millis", sa.Integer()))
    op.add_column("whoop_workouts", sa.Column("zone_two_millis", sa.Integer()))
    op.add_column("whoop_workouts", sa.Column("zone_three_millis", sa.Integer()))
    op.add_column("whoop_workouts", sa.Column("zone_four_millis", sa.Integer()))
    op.add_column("whoop_workouts", sa.Column("zone_five_millis", sa.Integer()))


def downgrade() -> None:
    op.drop_column("whoop_workouts", "zone_five_millis")
    op.drop_column("whoop_workouts", "zone_four_millis")
    op.drop_column("whoop_workouts", "zone_three_millis")
    op.drop_column("whoop_workouts", "zone_two_millis")
    op.drop_column("whoop_workouts", "zone_one_millis")
    op.drop_column("whoop_workouts", "zone_zero_millis")
    op.drop_column("whoop_workouts", "altitude_change_meters")
    op.drop_column("whoop_workouts", "percent_recorded")
    op.drop_column("whoop_workouts", "end_time")

    op.drop_column("whoop_sleep", "no_data_minutes")
    op.drop_column("whoop_sleep", "disturbance_count")
    op.drop_column("whoop_sleep", "sleep_cycle_count")
    op.drop_column("whoop_sleep", "sleep_need_nap_minutes")
    op.drop_column("whoop_sleep", "sleep_need_strain_minutes")
    op.drop_column("whoop_sleep", "sleep_need_debt_minutes")
    op.drop_column("whoop_sleep", "sleep_need_baseline_minutes")
