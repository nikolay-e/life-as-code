"""Add GarminTrainingStatus and WhoopCycle tables

Revision ID: 002_garmin_whoop
Revises: 001_check_constraints
Create Date: 2025-12-18

This migration adds:
1. garmin_training_status table for VO2Max, training load, fitness age, endurance score
2. whoop_cycles table for daily strain summaries
"""

from alembic import op
import sqlalchemy as sa


revision = "002_garmin_whoop"
down_revision = "001_check_constraints"
branch_labels = None
depends_on = None


def upgrade():
    # Create garmin_training_status table
    op.create_table(
        "garmin_training_status",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("vo2_max", sa.Float()),
        sa.Column("vo2_max_precise", sa.Float()),
        sa.Column("fitness_age", sa.Integer()),
        sa.Column("training_load_7_day", sa.Float()),
        sa.Column("acute_training_load", sa.Float()),
        sa.Column("training_status", sa.String(50)),
        sa.Column("training_status_description", sa.String(200)),
        sa.Column("primary_training_effect", sa.Float()),
        sa.Column("anaerobic_training_effect", sa.Float()),
        sa.Column("endurance_score", sa.Float()),
        sa.Column("total_kilocalories", sa.Float()),
        sa.Column("active_kilocalories", sa.Float()),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "date", name="_user_garmin_training_date_uc"),
    )

    op.create_index(
        "idx_garmin_training_user_date",
        "garmin_training_status",
        ["user_id", "date"],
        postgresql_using="btree",
    )

    # Add CHECK constraints for garmin_training_status
    op.execute(
        "ALTER TABLE garmin_training_status ADD CONSTRAINT valid_vo2_max_range "
        "CHECK ((vo2_max >= 10 AND vo2_max <= 100) OR vo2_max IS NULL)"
    )
    op.execute(
        "ALTER TABLE garmin_training_status ADD CONSTRAINT valid_fitness_age_range "
        "CHECK ((fitness_age >= 10 AND fitness_age <= 120) OR fitness_age IS NULL)"
    )
    op.execute(
        "ALTER TABLE garmin_training_status ADD CONSTRAINT valid_training_load_7_day "
        "CHECK ((training_load_7_day >= 0) OR training_load_7_day IS NULL)"
    )
    op.execute(
        "ALTER TABLE garmin_training_status ADD CONSTRAINT valid_acute_training_load "
        "CHECK ((acute_training_load >= 0) OR acute_training_load IS NULL)"
    )
    op.execute(
        "ALTER TABLE garmin_training_status ADD CONSTRAINT valid_endurance_score_range "
        "CHECK ((endurance_score >= 0 AND endurance_score <= 100) OR endurance_score IS NULL)"
    )
    op.execute(
        "ALTER TABLE garmin_training_status ADD CONSTRAINT valid_total_kilocalories "
        "CHECK ((total_kilocalories >= 0) OR total_kilocalories IS NULL)"
    )
    op.execute(
        "ALTER TABLE garmin_training_status ADD CONSTRAINT valid_active_kilocalories "
        "CHECK ((active_kilocalories >= 0) OR active_kilocalories IS NULL)"
    )

    # Create whoop_cycles table
    op.create_table(
        "whoop_cycles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("strain", sa.Float()),
        sa.Column("kilojoules", sa.Float()),
        sa.Column("avg_heart_rate", sa.Integer()),
        sa.Column("max_heart_rate", sa.Integer()),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "date", name="_user_whoop_cycle_date_uc"),
    )

    op.create_index(
        "idx_whoop_cycle_user_date",
        "whoop_cycles",
        ["user_id", "date"],
        postgresql_using="btree",
    )

    # Add CHECK constraints for whoop_cycles
    op.execute(
        "ALTER TABLE whoop_cycles ADD CONSTRAINT valid_cycle_strain_range "
        "CHECK ((strain >= 0 AND strain <= 21) OR strain IS NULL)"
    )
    op.execute(
        "ALTER TABLE whoop_cycles ADD CONSTRAINT valid_cycle_kilojoules "
        "CHECK ((kilojoules >= 0) OR kilojoules IS NULL)"
    )
    op.execute(
        "ALTER TABLE whoop_cycles ADD CONSTRAINT valid_cycle_avg_hr "
        "CHECK ((avg_heart_rate >= 30 AND avg_heart_rate <= 250) OR avg_heart_rate IS NULL)"
    )
    op.execute(
        "ALTER TABLE whoop_cycles ADD CONSTRAINT valid_cycle_max_hr "
        "CHECK ((max_heart_rate >= 40 AND max_heart_rate <= 250) OR max_heart_rate IS NULL)"
    )


def downgrade():
    op.drop_table("whoop_cycles")
    op.drop_table("garmin_training_status")
