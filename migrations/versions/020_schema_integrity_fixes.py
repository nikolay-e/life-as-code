"""Schema integrity fixes: unique constraints, FK indexes, Intervention.active boolean, drop orphaned body_battery

Revision ID: 020_schema_integrity
Revises: 019_add_updated_at
Create Date: 2026-03-21
"""

from alembic import op
import sqlalchemy as sa

revision = "020_schema_integrity"
down_revision = "019_add_updated_at"
branch_labels = None
depends_on = None


def upgrade():
    # 1a. Missing unique constraints
    op.create_unique_constraint(
        "_clinical_alert_user_type_status_detected_uc",
        "clinical_alert_events",
        ["user_id", "alert_type", "status", "first_detected_at"],
    )
    op.create_unique_constraint(
        "_longevity_goal_user_category_uc",
        "longevity_goals",
        ["user_id", "category"],
    )
    op.create_unique_constraint(
        "_intervention_user_name_start_category_uc",
        "interventions",
        ["user_id", "name", "start_date", "category"],
    )

    # 1b. Missing FK indexes (user_id columns that lack index=True)
    # UserCredentials.user_id already has unique=True which creates an index
    # UserSettings.user_id already has unique=True which creates an index
    # SyncProgress.user_id already has index from composite unique constraint
    # These are all covered — skip explicit index creation

    # 1c. Intervention.active: Integer -> Boolean
    op.add_column("interventions", sa.Column("active_bool", sa.Boolean(), nullable=True))
    op.execute("UPDATE interventions SET active_bool = (active = 1)")
    op.drop_constraint("valid_intervention_active", "interventions", type_="check")
    op.drop_column("interventions", "active")
    op.alter_column("interventions", "active_bool", new_column_name="active")
    op.alter_column(
        "interventions",
        "active",
        nullable=False,
        server_default=sa.text("true"),
    )

    # Recreate index dropped with the old active column
    op.create_index("idx_intervention_user_active", "interventions", ["user_id", "active"])

    # 1d. Drop orphaned body_battery table (constraints created in 001 but no ORM model)
    op.execute("DROP TABLE IF EXISTS body_battery")

    # 1e. Date range constraint for Intervention
    op.create_check_constraint(
        "valid_intervention_dates",
        "interventions",
        "end_date IS NULL OR end_date >= start_date",
    )


def downgrade():
    op.drop_constraint("valid_intervention_dates", "interventions", type_="check")

    # Revert active back to Integer
    op.drop_index("idx_intervention_user_active", "interventions")
    op.add_column("interventions", sa.Column("active_int", sa.Integer(), nullable=True))
    op.execute("UPDATE interventions SET active_int = CASE WHEN active THEN 1 ELSE 0 END")
    op.drop_column("interventions", "active")
    op.alter_column("interventions", "active_int", new_column_name="active")
    op.alter_column(
        "interventions",
        "active",
        nullable=False,
        server_default=sa.text("1"),
    )
    op.create_check_constraint(
        "valid_intervention_active",
        "interventions",
        "active IN (0, 1)",
    )
    op.create_index("idx_intervention_user_active", "interventions", ["user_id", "active"])

    op.drop_constraint(
        "_intervention_user_name_start_category_uc", "interventions", type_="unique"
    )
    op.drop_constraint(
        "_longevity_goal_user_category_uc", "longevity_goals", type_="unique"
    )
    op.drop_constraint(
        "_clinical_alert_user_type_status_detected_uc",
        "clinical_alert_events",
        type_="unique",
    )
