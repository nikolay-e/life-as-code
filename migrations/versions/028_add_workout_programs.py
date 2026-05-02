"""Add workout programs, program days/exercises, and Hevy exercise template cache

Revision ID: 028_workout_programs
Revises: 027_sleep_start_end_times
Create Date: 2026-05-02

Adds the user-defined training program tracker:

- `exercise_templates` caches the Hevy exercise catalog per user. Hevy templates
  are scoped to the account (so custom user exercises are visible alongside
  Hevy's library), so we store one row per (user_id, hevy_template_id) and
  refresh on demand from /v1/exercise_templates.

- `workout_programs` is the mesocycle / program parent (name, dates, goal,
  active flag). A partial unique index guarantees only one active program per
  user; archival flips `is_active=false` and stamps `end_date` + `archived_at`,
  keeping completed programs as immutable history.

- `program_days` are the training days within a program (Push, Pull, Legs, ...).

- `program_exercises` carry the prescription: target sets, rep range, RPE
  range, prescribed weight, rest, tempo, and free-text notes (accents / cues).
  `template_id` points at the cached Hevy template so logged sets (matched by
  exercise title) can later be reconciled against the program plan.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "028_workout_programs"
down_revision: str | None = "027_sleep_start_end_times"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "exercise_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("hevy_template_id", sa.String(100), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("exercise_type", sa.String(50)),
        sa.Column("primary_muscle_group", sa.String(80)),
        sa.Column("secondary_muscle_groups", sa.dialects.postgresql.JSONB()),
        sa.Column("equipment", sa.String(80)),
        sa.Column(
            "is_custom",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "last_synced_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint(
            "user_id", "hevy_template_id", name="_user_hevy_template_uc"
        ),
    )
    op.create_index(
        "idx_exercise_template_user_title",
        "exercise_templates",
        ["user_id", "title"],
    )

    op.create_table(
        "workout_programs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("goal", sa.String(80)),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date()),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("archived_at", sa.DateTime()),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "end_date IS NULL OR end_date >= start_date",
            name="valid_program_date_range",
        ),
    )
    op.create_index(
        "idx_workout_program_user_started",
        "workout_programs",
        ["user_id", "start_date"],
    )
    # Partial unique index: at most one active program per user.
    op.create_index(
        "ux_workout_program_one_active_per_user",
        "workout_programs",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )

    op.create_table(
        "program_days",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "program_id",
            sa.Integer(),
            sa.ForeignKey("workout_programs.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("day_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("focus", sa.String(200)),
        sa.Column("notes", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint("program_id", "day_order", name="_program_day_order_uc"),
    )

    op.create_table(
        "program_exercises",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "day_id",
            sa.Integer(),
            sa.ForeignKey("program_days.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "template_id",
            sa.Integer(),
            sa.ForeignKey("exercise_templates.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "exercise_order", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("exercise_title", sa.String(200), nullable=False),
        sa.Column("target_sets", sa.Integer()),
        sa.Column("target_reps_min", sa.Integer()),
        sa.Column("target_reps_max", sa.Integer()),
        sa.Column("target_rpe_min", sa.Float()),
        sa.Column("target_rpe_max", sa.Float()),
        sa.Column("target_weight_kg", sa.Float()),
        sa.Column("rest_seconds", sa.Integer()),
        sa.Column("tempo", sa.String(20)),
        sa.Column("notes", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint(
            "day_id", "exercise_order", name="_program_exercise_order_uc"
        ),
        sa.CheckConstraint(
            "target_sets IS NULL OR target_sets >= 0",
            name="valid_program_target_sets",
        ),
        sa.CheckConstraint(
            "target_reps_min IS NULL OR target_reps_min >= 0",
            name="valid_program_target_reps_min",
        ),
        sa.CheckConstraint(
            "target_reps_max IS NULL OR target_reps_max >= 0",
            name="valid_program_target_reps_max",
        ),
        sa.CheckConstraint(
            "target_reps_min IS NULL OR target_reps_max IS NULL "
            "OR target_reps_max >= target_reps_min",
            name="valid_program_reps_window",
        ),
        sa.CheckConstraint(
            "(target_rpe_min IS NULL OR (target_rpe_min >= 1 AND target_rpe_min <= 10))",
            name="valid_program_target_rpe_min",
        ),
        sa.CheckConstraint(
            "(target_rpe_max IS NULL OR (target_rpe_max >= 1 AND target_rpe_max <= 10))",
            name="valid_program_target_rpe_max",
        ),
        sa.CheckConstraint(
            "target_rpe_min IS NULL OR target_rpe_max IS NULL "
            "OR target_rpe_max >= target_rpe_min",
            name="valid_program_rpe_window",
        ),
        sa.CheckConstraint(
            "target_weight_kg IS NULL OR target_weight_kg >= 0",
            name="valid_program_target_weight",
        ),
        sa.CheckConstraint(
            "rest_seconds IS NULL OR rest_seconds >= 0",
            name="valid_program_rest_seconds",
        ),
    )


def downgrade() -> None:
    op.drop_table("program_exercises")
    op.drop_table("program_days")
    op.drop_index(
        "ux_workout_program_one_active_per_user", table_name="workout_programs"
    )
    op.drop_index("idx_workout_program_user_started", table_name="workout_programs")
    op.drop_table("workout_programs")
    op.drop_index(
        "idx_exercise_template_user_title", table_name="exercise_templates"
    )
    op.drop_table("exercise_templates")
