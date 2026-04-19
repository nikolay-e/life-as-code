"""Add eight_sleep to source check constraints

Revision ID: 024_eight_sleep_source
Revises: b25d549903fc
Create Date: 2026-04-19 11:45:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "024_eight_sleep_source"
down_revision: str | None = "b25d549903fc"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES_AND_CONSTRAINTS = [
    ("hrv", "valid_hrv_source"),
    ("heart_rate", "valid_heart_rate_source"),
    ("sleep", "valid_sleep_source"),
]

OLD_SOURCES = "ARRAY['garmin','google','apple_health','hevy','whoop']"
NEW_SOURCES = "ARRAY['garmin','google','apple_health','hevy','whoop','eight_sleep']"


def upgrade() -> None:
    for table, constraint in TABLES_AND_CONSTRAINTS:
        op.drop_constraint(constraint, table, type_="check")
        op.create_check_constraint(
            constraint,
            table,
            f"source = ANY({NEW_SOURCES})",
        )


def downgrade() -> None:
    for table, constraint in TABLES_AND_CONSTRAINTS:
        op.drop_constraint(constraint, table, type_="check")
        op.create_check_constraint(
            constraint,
            table,
            f"source = ANY({OLD_SOURCES})",
        )
