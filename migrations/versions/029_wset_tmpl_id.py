"""Add exercise_template_id to workout_sets

Revision ID: 029_wset_tmpl_id
Revises: 028_workout_programs
Create Date: 2026-05-02

Hevy's /v1/workouts response includes a stable `exercise_template_id` for each
exercise inside a workout. Until now the sync discarded that id and kept only
the exercise title, which means matching a logged set back to a programmed
exercise relied on string equality (fragile to renames, translations,
custom-template edits).

Storing the template id directly on `workout_sets` makes the program ↔ log
linkage robust: ProgramExercise.template_id (FK → exercise_templates.id) and
WorkoutSet.exercise_template_id (raw Hevy id) can be joined via the same
`exercise_templates.hevy_template_id` column.

Backfill is intentionally skipped — historical rows keep NULL until they are
re-synced. The column is indexed alongside `user_id` to support per-user
program-vs-actual queries.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "029_wset_tmpl_id"
down_revision: str | None = "028_workout_programs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "workout_sets",
        sa.Column("exercise_template_id", sa.String(100), nullable=True),
    )
    op.create_index(
        "idx_workout_user_template",
        "workout_sets",
        ["user_id", "exercise_template_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_workout_user_template", table_name="workout_sets")
    op.drop_column("workout_sets", "exercise_template_id")
