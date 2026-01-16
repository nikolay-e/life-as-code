"""Add training_readiness_score to garmin_training_status

Revision ID: 012_add_training_readiness
Revises: 011_add_garmin_activities
Create Date: 2026-01-16

Adds training_readiness_score column to garmin_training_status table.
This stores the Garmin Training Readiness score (0-100) which is comparable
to Whoop Recovery score.
"""

from alembic import op
import sqlalchemy as sa


revision = "012_add_training_readiness"
down_revision = "011_add_garmin_activities"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "garmin_training_status",
        sa.Column("training_readiness_score", sa.Float(), nullable=True),
    )

    op.execute(
        """
        ALTER TABLE garmin_training_status
        ADD CONSTRAINT valid_training_readiness_score_range
        CHECK ((training_readiness_score >= 0 AND training_readiness_score <= 100) OR training_readiness_score IS NULL);
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE garmin_training_status
        DROP CONSTRAINT IF EXISTS valid_training_readiness_score_range;
        """
    )
    op.drop_column("garmin_training_status", "training_readiness_score")
