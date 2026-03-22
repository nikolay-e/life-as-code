"""Fix user_calibrating column type: integer -> boolean

Revision ID: 022_fix_calibrating
Revises: 021_fix_snapshot_alert
Create Date: 2026-03-22
"""

from alembic import op

revision = "022_fix_calibrating"
down_revision = "021_fix_snapshot_alert"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE whoop_recovery "
        "ALTER COLUMN user_calibrating TYPE boolean "
        "USING user_calibrating::boolean"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE whoop_recovery "
        "ALTER COLUMN user_calibrating TYPE integer "
        "USING user_calibrating::integer"
    )
