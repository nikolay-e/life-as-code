"""Add predictions and anomalies tables for ML pipeline

Revision ID: 014_add_predictions_anomalies
Revises: 013_add_source_to_stress
Create Date: 2025-02-14

Adds tables for ML-generated forecasts (Chronos) and anomaly detection (Isolation Forest).
"""

from alembic import op
import sqlalchemy as sa

revision = "014_add_predictions_anomalies"
down_revision = "013_add_source_to_stress"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "predictions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("metric", sa.String(50), nullable=False),
        sa.Column("target_date", sa.Date(), nullable=False),
        sa.Column("horizon_days", sa.Integer(), nullable=False),
        sa.Column("p10", sa.Float()),
        sa.Column("p50", sa.Float()),
        sa.Column("p90", sa.Float()),
        sa.Column("model_version", sa.String(100)),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.UniqueConstraint(
            "user_id", "metric", "target_date", "horizon_days",
            name="_user_prediction_uc",
        ),
        sa.Index(
            "idx_prediction_user_metric",
            "user_id", "metric", "target_date",
        ),
        sa.CheckConstraint("horizon_days > 0", name="valid_horizon_days"),
    )

    op.create_table(
        "anomalies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("anomaly_score", sa.Float(), nullable=False),
        sa.Column("contributing_factors", sa.JSON()),
        sa.Column("model_version", sa.String(100)),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.UniqueConstraint("user_id", "date", name="_user_anomaly_date_uc"),
        sa.Index(
            "idx_anomaly_user_date",
            "user_id", "date",
            postgresql_ops={"date": "DESC"},
        ),
        sa.CheckConstraint(
            "anomaly_score >= 0 AND anomaly_score <= 1",
            name="valid_anomaly_score",
        ),
    )


def downgrade() -> None:
    op.drop_table("anomalies")
    op.drop_table("predictions")
