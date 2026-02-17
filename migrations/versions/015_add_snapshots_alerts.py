"""Add health_snapshots and clinical_alert_events tables

Revision ID: 015_add_snapshots_alerts
Revises: 014_add_predictions_anomalies
Create Date: 2026-02-17

Materialized analytics snapshots and clinical alert lifecycle tracking.
"""

from alembic import op
import sqlalchemy as sa

revision = "015_add_snapshots_alerts"
down_revision = "014_add_predictions_anomalies"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "health_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("mode", sa.String(20), nullable=False, server_default="recent"),
        sa.Column("snapshot_json", sa.JSON(), nullable=False),
        sa.Column("health_score", sa.Float()),
        sa.Column(
            "computed_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")
        ),
        sa.UniqueConstraint(
            "user_id", "date", "mode", name="_user_snapshot_date_mode_uc"
        ),
        sa.Index(
            "idx_snapshot_user_date",
            "user_id",
            "date",
            postgresql_ops={"date": "DESC"},
        ),
        sa.CheckConstraint(
            "mode IN ('recent', 'quarter', 'year', 'all')",
            name="valid_snapshot_mode",
        ),
    )

    op.create_table(
        "clinical_alert_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("alert_type", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False, server_default="warning"),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("details_json", sa.JSON()),
        sa.Column(
            "first_detected_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "last_detected_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("acknowledged_at", sa.DateTime()),
        sa.Column("resolved_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.Index("idx_alert_user_status", "user_id", "status"),
        sa.Index("idx_alert_user_type", "user_id", "alert_type"),
        sa.CheckConstraint(
            "severity IN ('info', 'warning', 'alert', 'critical')",
            name="valid_alert_severity",
        ),
        sa.CheckConstraint(
            "status IN ('open', 'acknowledged', 'resolved')",
            name="valid_alert_status",
        ),
    )


def downgrade() -> None:
    op.drop_table("clinical_alert_events")
    op.drop_table("health_snapshots")
