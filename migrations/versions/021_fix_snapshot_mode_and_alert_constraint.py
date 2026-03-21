"""Fix clinical alert unique constraint

Revision ID: 021_fix_snapshot_alert
Revises: 020_schema_integrity
Create Date: 2026-03-21
"""

from alembic import op

revision = "021_fix_snapshot_alert"
down_revision = "020_schema_integrity"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint(
        "_clinical_alert_user_type_status_detected_uc",
        "clinical_alert_events",
        type_="unique",
    )
    op.create_unique_constraint(
        "_clinical_alert_user_type_detected_uc",
        "clinical_alert_events",
        ["user_id", "alert_type", "first_detected_at"],
    )


def downgrade():
    op.drop_constraint(
        "_clinical_alert_user_type_detected_uc",
        "clinical_alert_events",
        type_="unique",
    )
    op.create_unique_constraint(
        "_clinical_alert_user_type_status_detected_uc",
        "clinical_alert_events",
        ["user_id", "alert_type", "status", "first_detected_at"],
    )
