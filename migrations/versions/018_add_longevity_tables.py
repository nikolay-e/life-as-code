"""Add longevity tracking tables and user profile fields

Revision ID: 018_add_longevity_tables
Revises: 017_add_garmin_fields
Create Date: 2026-03-18

New columns: user_settings.birth_date, user_settings.gender
New tables: blood_biomarkers, interventions, functional_tests, longevity_goals
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON

revision = "018_add_longevity_tables"
down_revision = "017_add_garmin_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user_settings", sa.Column("birth_date", sa.Date()))
    op.add_column("user_settings", sa.Column("gender", sa.String(10)))

    op.create_table(
        "blood_biomarkers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("date", sa.Date(), nullable=False, index=True),
        sa.Column("marker_name", sa.String(100), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(50), nullable=False),
        sa.Column("reference_range_low", sa.Float()),
        sa.Column("reference_range_high", sa.Float()),
        sa.Column("longevity_optimal_low", sa.Float()),
        sa.Column("longevity_optimal_high", sa.Float()),
        sa.Column("lab_name", sa.String(200)),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime()),
        sa.UniqueConstraint("user_id", "date", "marker_name", name="_user_biomarker_date_marker_uc"),
    )
    op.create_index("idx_biomarker_user_date", "blood_biomarkers", ["user_id", "date"])
    op.create_index("idx_biomarker_user_marker", "blood_biomarkers", ["user_id", "marker_name"])

    op.create_table(
        "interventions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date()),
        sa.Column("dosage", sa.String(100)),
        sa.Column("frequency", sa.String(100)),
        sa.Column("target_metrics", JSON()),
        sa.Column("notes", sa.Text()),
        sa.Column("active", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
        sa.CheckConstraint(
            "category IN ('supplement', 'protocol', 'medication', 'lifestyle', 'diet')",
            name="valid_intervention_category",
        ),
        sa.CheckConstraint("active IN (0, 1)", name="valid_intervention_active"),
    )
    op.create_index("idx_intervention_user_active", "interventions", ["user_id", "active"])

    op.create_table(
        "functional_tests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("date", sa.Date(), nullable=False, index=True),
        sa.Column("test_name", sa.String(100), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(50), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime()),
        sa.UniqueConstraint("user_id", "date", "test_name", name="_user_functest_date_name_uc"),
    )
    op.create_index("idx_functest_user_date", "functional_tests", ["user_id", "date"])
    op.create_index("idx_functest_user_test", "functional_tests", ["user_id", "test_name"])

    op.create_table(
        "longevity_goals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("target_value", sa.Float()),
        sa.Column("current_value", sa.Float()),
        sa.Column("unit", sa.String(50)),
        sa.Column("target_age", sa.Integer()),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )
    op.create_index("idx_longevity_goal_user", "longevity_goals", ["user_id"])


def downgrade() -> None:
    op.drop_index("idx_longevity_goal_user", table_name="longevity_goals")
    op.drop_table("longevity_goals")

    op.drop_index("idx_functest_user_test", table_name="functional_tests")
    op.drop_index("idx_functest_user_date", table_name="functional_tests")
    op.drop_table("functional_tests")

    op.drop_index("idx_intervention_user_active", table_name="interventions")
    op.drop_table("interventions")

    op.drop_index("idx_biomarker_user_marker", table_name="blood_biomarkers")
    op.drop_index("idx_biomarker_user_date", table_name="blood_biomarkers")
    op.drop_table("blood_biomarkers")

    op.drop_column("user_settings", "gender")
    op.drop_column("user_settings", "birth_date")
