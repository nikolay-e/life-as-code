"""Add garmin_activities table

Revision ID: 011_add_garmin_activities
Revises: 010_add_source_to_data_tables
Create Date: 2026-01-16

Adds garmin_activities table for storing individual Garmin activity records.
"""

from alembic import op
import sqlalchemy as sa


revision = "011_add_garmin_activities"
down_revision = "010_add_source_to_data_tables"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "garmin_activities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True
        ),
        sa.Column("activity_id", sa.String(50), nullable=False),
        sa.Column("date", sa.Date(), nullable=False, index=True),
        sa.Column("start_time", sa.DateTime(), nullable=False),
        sa.Column("activity_type", sa.String(100)),
        sa.Column("activity_name", sa.String(200)),
        sa.Column("duration_seconds", sa.Integer()),
        sa.Column("distance_meters", sa.Float()),
        sa.Column("avg_heart_rate", sa.Integer()),
        sa.Column("max_heart_rate", sa.Integer()),
        sa.Column("calories", sa.Integer()),
        sa.Column("avg_speed_mps", sa.Float()),
        sa.Column("max_speed_mps", sa.Float()),
        sa.Column("elevation_gain_meters", sa.Float()),
        sa.Column("elevation_loss_meters", sa.Float()),
        sa.Column("avg_power_watts", sa.Float()),
        sa.Column("max_power_watts", sa.Float()),
        sa.Column("training_effect_aerobic", sa.Float()),
        sa.Column("training_effect_anaerobic", sa.Float()),
        sa.Column("vo2_max_value", sa.Float()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_unique_constraint(
        "_user_garmin_activity_uc", "garmin_activities", ["user_id", "activity_id"]
    )

    op.create_index(
        "idx_garmin_activity_user_date",
        "garmin_activities",
        ["user_id", sa.text("date DESC")],
    )

    op.execute(
        """
        ALTER TABLE garmin_activities
        ADD CONSTRAINT valid_garmin_duration CHECK ((duration_seconds >= 0) OR duration_seconds IS NULL);
        """
    )
    op.execute(
        """
        ALTER TABLE garmin_activities
        ADD CONSTRAINT valid_garmin_distance CHECK ((distance_meters >= 0) OR distance_meters IS NULL);
        """
    )
    op.execute(
        """
        ALTER TABLE garmin_activities
        ADD CONSTRAINT valid_garmin_activity_avg_hr CHECK ((avg_heart_rate >= 30 AND avg_heart_rate <= 250) OR avg_heart_rate IS NULL);
        """
    )
    op.execute(
        """
        ALTER TABLE garmin_activities
        ADD CONSTRAINT valid_garmin_activity_max_hr CHECK ((max_heart_rate >= 40 AND max_heart_rate <= 250) OR max_heart_rate IS NULL);
        """
    )
    op.execute(
        """
        ALTER TABLE garmin_activities
        ADD CONSTRAINT valid_garmin_calories CHECK ((calories >= 0) OR calories IS NULL);
        """
    )
    op.execute(
        """
        ALTER TABLE garmin_activities
        ADD CONSTRAINT valid_garmin_te_aerobic CHECK ((training_effect_aerobic >= 0 AND training_effect_aerobic <= 5) OR training_effect_aerobic IS NULL);
        """
    )
    op.execute(
        """
        ALTER TABLE garmin_activities
        ADD CONSTRAINT valid_garmin_te_anaerobic CHECK ((training_effect_anaerobic >= 0 AND training_effect_anaerobic <= 5) OR training_effect_anaerobic IS NULL);
        """
    )


def downgrade():
    op.drop_table("garmin_activities")
