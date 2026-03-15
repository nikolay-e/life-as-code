"""Add Garmin HR zones, SpO2, respiration, and race predictions

Revision ID: 017_add_garmin_fields
Revises: 016_add_whoop_fields
Create Date: 2026-02-21

Activities: 5 HR zone duration columns
HeartRate: SpO2 avg/min, respiratory rate (waking/lowest/highest)
New table: garmin_race_predictions
"""

from alembic import op
import sqlalchemy as sa

revision = "017_add_garmin_fields"
down_revision = "016_add_whoop_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("garmin_activities", sa.Column("hr_zone_one_seconds", sa.Integer()))
    op.add_column("garmin_activities", sa.Column("hr_zone_two_seconds", sa.Integer()))
    op.add_column("garmin_activities", sa.Column("hr_zone_three_seconds", sa.Integer()))
    op.add_column("garmin_activities", sa.Column("hr_zone_four_seconds", sa.Integer()))
    op.add_column("garmin_activities", sa.Column("hr_zone_five_seconds", sa.Integer()))

    op.add_column("heart_rate", sa.Column("spo2_avg", sa.Float()))
    op.add_column("heart_rate", sa.Column("spo2_min", sa.Float()))
    op.add_column("heart_rate", sa.Column("waking_respiratory_rate", sa.Float()))
    op.add_column("heart_rate", sa.Column("lowest_respiratory_rate", sa.Float()))
    op.add_column("heart_rate", sa.Column("highest_respiratory_rate", sa.Float()))

    op.create_check_constraint(
        "valid_hr_spo2_avg_range", "heart_rate",
        "(spo2_avg >= 50 AND spo2_avg <= 100) OR spo2_avg IS NULL",
    )
    op.create_check_constraint(
        "valid_hr_spo2_min_range", "heart_rate",
        "(spo2_min >= 50 AND spo2_min <= 100) OR spo2_min IS NULL",
    )
    op.create_check_constraint(
        "valid_waking_resp_rate_range", "heart_rate",
        "(waking_respiratory_rate >= 5 AND waking_respiratory_rate <= 50) OR waking_respiratory_rate IS NULL",
    )
    op.create_check_constraint(
        "valid_lowest_resp_rate_range", "heart_rate",
        "(lowest_respiratory_rate >= 5 AND lowest_respiratory_rate <= 50) OR lowest_respiratory_rate IS NULL",
    )
    op.create_check_constraint(
        "valid_highest_resp_rate_range", "heart_rate",
        "(highest_respiratory_rate >= 5 AND highest_respiratory_rate <= 50) OR highest_respiratory_rate IS NULL",
    )

    op.create_table(
        "garmin_race_predictions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("date", sa.Date(), nullable=False, index=True),
        sa.Column("prediction_5k_seconds", sa.Integer()),
        sa.Column("prediction_10k_seconds", sa.Integer()),
        sa.Column("prediction_half_marathon_seconds", sa.Integer()),
        sa.Column("prediction_marathon_seconds", sa.Integer()),
        sa.Column("vo2_max_value", sa.Float()),
        sa.Column("created_at", sa.DateTime()),
        sa.UniqueConstraint("user_id", "date", name="_user_garmin_race_pred_date_uc"),
        sa.CheckConstraint("(prediction_5k_seconds > 0) OR prediction_5k_seconds IS NULL", name="valid_pred_5k"),
        sa.CheckConstraint("(prediction_10k_seconds > 0) OR prediction_10k_seconds IS NULL", name="valid_pred_10k"),
        sa.CheckConstraint("(prediction_half_marathon_seconds > 0) OR prediction_half_marathon_seconds IS NULL", name="valid_pred_half"),
        sa.CheckConstraint("(prediction_marathon_seconds > 0) OR prediction_marathon_seconds IS NULL", name="valid_pred_marathon"),
        sa.CheckConstraint("(vo2_max_value >= 10 AND vo2_max_value <= 100) OR vo2_max_value IS NULL", name="valid_race_pred_vo2_max"),
    )
    op.create_index(
        "idx_garmin_race_pred_user_date",
        "garmin_race_predictions",
        ["user_id", sa.text("date DESC")],
    )


def downgrade() -> None:
    op.drop_index("idx_garmin_race_pred_user_date", table_name="garmin_race_predictions")
    op.drop_table("garmin_race_predictions")

    op.drop_constraint("valid_highest_resp_rate_range", "heart_rate", type_="check")
    op.drop_constraint("valid_lowest_resp_rate_range", "heart_rate", type_="check")
    op.drop_constraint("valid_waking_resp_rate_range", "heart_rate", type_="check")
    op.drop_constraint("valid_hr_spo2_min_range", "heart_rate", type_="check")
    op.drop_constraint("valid_hr_spo2_avg_range", "heart_rate", type_="check")

    op.drop_column("heart_rate", "highest_respiratory_rate")
    op.drop_column("heart_rate", "lowest_respiratory_rate")
    op.drop_column("heart_rate", "waking_respiratory_rate")
    op.drop_column("heart_rate", "spo2_min")
    op.drop_column("heart_rate", "spo2_avg")

    op.drop_column("garmin_activities", "hr_zone_five_seconds")
    op.drop_column("garmin_activities", "hr_zone_four_seconds")
    op.drop_column("garmin_activities", "hr_zone_three_seconds")
    op.drop_column("garmin_activities", "hr_zone_two_seconds")
    op.drop_column("garmin_activities", "hr_zone_one_seconds")
