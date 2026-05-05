"""Extend health_events, add vitals + subjective_ratings + bowel_movements,
extend food_logs with drink columns, install pg_trgm for fuzzy search.

Revision ID: 034_extend_health_log
Revises: 033_add_food_diary
Create Date: 2026-05-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

_USERS_FK = "users.id"

revision: str = "034_extend_health_log"
down_revision: str | None = "033_add_food_diary"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


VITAL_KINDS = (
    "bp_sys",
    "bp_dia",
    "spo2",
    "glucose_mg_dl",
    "glucose_mmol_l",
    "ketones_mmol_l",
    "temp_c",
    "resting_hr_bpm",
    "respiratory_rate",
    "weight_kg",
    "body_fat_pct",
)

SUBJECTIVE_DIMENSIONS = (
    "mood",
    "energy",
    "focus",
    "anxiety",
    "stress",
    "libido",
    "motivation",
    "sleep_quality",
    "soreness",
    "pain",
)


def _enum_check(column: str, values: tuple[str, ...]) -> str:
    quoted = ", ".join(f"'{v}'" for v in values)
    return f"{column} IN ({quoted})"


def upgrade() -> None:
    op.add_column(
        "health_events",
        sa.Column("intensity", sa.SmallInteger(), nullable=True),
    )
    op.add_column(
        "health_events",
        sa.Column("valence", sa.SmallInteger(), nullable=True),
    )
    op.add_column(
        "health_events",
        sa.Column("body_location", sa.Text(), nullable=True),
    )
    op.add_column(
        "health_events",
        sa.Column("duration_min", sa.Integer(), nullable=True),
    )
    op.add_column(
        "health_events",
        sa.Column(
            "related_event_id",
            sa.BigInteger(),
            sa.ForeignKey(
                "health_events.id",
                ondelete="SET NULL",
                name="fk_health_events_related_event",
            ),
            nullable=True,
        ),
    )
    op.add_column(
        "health_events",
        sa.Column(
            "related_workout_set_id",
            sa.Integer(),
            sa.ForeignKey(
                "workout_sets.id",
                ondelete="SET NULL",
                name="fk_health_events_related_workout_set",
            ),
            nullable=True,
        ),
    )
    op.create_check_constraint(
        "valid_health_event_intensity",
        "health_events",
        "intensity IS NULL OR (intensity BETWEEN 0 AND 10)",
    )
    op.create_check_constraint(
        "valid_health_event_valence",
        "health_events",
        "valence IS NULL OR (valence BETWEEN -5 AND 5)",
    )
    op.create_check_constraint(
        "valid_health_event_duration_min",
        "health_events",
        "duration_min IS NULL OR duration_min >= 0",
    )

    op.add_column(
        "food_logs",
        sa.Column("alcohol_g", sa.Float(), nullable=True),
    )
    op.add_column(
        "food_logs",
        sa.Column("caffeine_mg", sa.Float(), nullable=True),
    )
    op.add_column(
        "food_logs",
        sa.Column("water_ml", sa.Float(), nullable=True),
    )
    op.create_check_constraint(
        "valid_food_log_alcohol_g",
        "food_logs",
        "alcohol_g IS NULL OR alcohol_g >= 0",
    )
    op.create_check_constraint(
        "valid_food_log_caffeine_mg",
        "food_logs",
        "caffeine_mg IS NULL OR caffeine_mg >= 0",
    )
    op.create_check_constraint(
        "valid_food_log_water_ml",
        "food_logs",
        "water_ml IS NULL OR water_ml >= 0",
    )

    op.create_table(
        "vitals",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey(_USERS_FK, ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("measured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("kind", sa.String(50), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(50), nullable=True),
        sa.Column("source", sa.String(50), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            _enum_check("kind", VITAL_KINDS),
            name="valid_vital_kind",
        ),
    )
    op.create_index(
        "idx_vitals_user_measured", "vitals", ["user_id", "measured_at"]
    )
    op.create_index(
        "idx_vitals_user_kind_measured",
        "vitals",
        ["user_id", "kind", "measured_at"],
    )

    op.create_table(
        "subjective_ratings",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey(_USERS_FK, ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("measured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("dimension", sa.String(50), nullable=False),
        sa.Column("score", sa.SmallInteger(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            _enum_check("dimension", SUBJECTIVE_DIMENSIONS),
            name="valid_subjective_dimension",
        ),
        sa.CheckConstraint(
            "score BETWEEN 1 AND 10",
            name="valid_subjective_score",
        ),
    )
    op.create_index(
        "idx_subjective_user_measured",
        "subjective_ratings",
        ["user_id", "measured_at"],
    )
    op.create_index(
        "idx_subjective_user_dim_measured",
        "subjective_ratings",
        ["user_id", "dimension", "measured_at"],
    )

    op.create_table(
        "bowel_movements",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey(_USERS_FK, ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("bristol_scale", sa.SmallInteger(), nullable=True),
        sa.Column("urgency", sa.SmallInteger(), nullable=True),
        sa.Column("blood", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "bristol_scale IS NULL OR (bristol_scale BETWEEN 1 AND 7)",
            name="valid_bowel_bristol",
        ),
        sa.CheckConstraint(
            "urgency IS NULL OR (urgency BETWEEN 1 AND 5)",
            name="valid_bowel_urgency",
        ),
    )
    op.create_index(
        "idx_bowel_user_occurred",
        "bowel_movements",
        ["user_id", "occurred_at"],
    )

    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_health_events_name_trgm "
        "ON health_events USING gin (name gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_health_events_notes_trgm "
        "ON health_events USING gin (notes gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_health_notes_text_trgm "
        "ON health_notes USING gin (text gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_food_products_name_trgm "
        "ON food_products USING gin (name gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_protocols_name_trgm "
        "ON protocols USING gin (name gin_trgm_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_protocols_name_trgm")
    op.execute("DROP INDEX IF EXISTS idx_food_products_name_trgm")
    op.execute("DROP INDEX IF EXISTS idx_health_notes_text_trgm")
    op.execute("DROP INDEX IF EXISTS idx_health_events_notes_trgm")
    op.execute("DROP INDEX IF EXISTS idx_health_events_name_trgm")

    op.drop_index("idx_bowel_user_occurred", table_name="bowel_movements")
    op.drop_table("bowel_movements")

    op.drop_index(
        "idx_subjective_user_dim_measured", table_name="subjective_ratings"
    )
    op.drop_index(
        "idx_subjective_user_measured", table_name="subjective_ratings"
    )
    op.drop_table("subjective_ratings")

    op.drop_index("idx_vitals_user_kind_measured", table_name="vitals")
    op.drop_index("idx_vitals_user_measured", table_name="vitals")
    op.drop_table("vitals")

    op.drop_constraint(
        "valid_food_log_water_ml", "food_logs", type_="check"
    )
    op.drop_constraint(
        "valid_food_log_caffeine_mg", "food_logs", type_="check"
    )
    op.drop_constraint(
        "valid_food_log_alcohol_g", "food_logs", type_="check"
    )
    op.drop_column("food_logs", "water_ml")
    op.drop_column("food_logs", "caffeine_mg")
    op.drop_column("food_logs", "alcohol_g")

    op.drop_constraint(
        "valid_health_event_duration_min", "health_events", type_="check"
    )
    op.drop_constraint(
        "valid_health_event_valence", "health_events", type_="check"
    )
    op.drop_constraint(
        "valid_health_event_intensity", "health_events", type_="check"
    )
    op.drop_constraint(
        "fk_health_events_related_workout_set",
        "health_events",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_health_events_related_event", "health_events", type_="foreignkey"
    )
    op.drop_column("health_events", "related_workout_set_id")
    op.drop_column("health_events", "related_event_id")
    op.drop_column("health_events", "duration_min")
    op.drop_column("health_events", "body_location")
    op.drop_column("health_events", "valence")
    op.drop_column("health_events", "intensity")
