"""Backfill health_events and protocols from interventions

Revision ID: 031_backfill_health_log
Revises: 030_add_health_log_tables
Create Date: 2026-05-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "031_backfill_health_log"
down_revision: str | None = "030_add_health_log_tables"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_POINT_EVENT_CONDITION = """
    (end_date IS NOT NULL AND start_date = end_date)
    OR (end_date IS NULL AND frequency IS NULL AND dosage IS NULL)
"""

_EVENT_DOMAIN_MAP = """
    CASE category
        WHEN 'supplement' THEN 'substance'
        WHEN 'medication' THEN 'medication'
        WHEN 'lifestyle'  THEN 'substance'
        WHEN 'diet'       THEN 'nutrition'
        WHEN 'protocol'   THEN 'therapy'
        ELSE                   'therapy'
    END
"""

_PROTOCOL_DOMAIN_MAP = """
    CASE category
        WHEN 'supplement' THEN 'supplement'
        WHEN 'medication' THEN 'medication'
        WHEN 'lifestyle'  THEN 'lifestyle'
        WHEN 'diet'       THEN 'diet'
        WHEN 'protocol'   THEN 'other'
        ELSE                   'other'
    END
"""


def upgrade() -> None:
    op.execute(
        sa.text(
            f"""
            INSERT INTO health_events (user_id, domain, name, start_ts, end_ts, dosage, notes,
                                       attributes, tags)
            SELECT
                user_id,
                {_EVENT_DOMAIN_MAP},
                name,
                start_date::timestamptz,
                NULL,
                dosage,
                notes,
                '{{}}'::jsonb,
                '[]'::jsonb
            FROM interventions
            WHERE {_POINT_EVENT_CONDITION}
            """
        )
    )

    op.execute(
        sa.text(
            f"""
            INSERT INTO protocols (user_id, name, domain, start_date, end_date, dosage,
                                   frequency, notes, tags)
            SELECT
                user_id,
                name,
                {_PROTOCOL_DOMAIN_MAP},
                start_date,
                end_date,
                dosage,
                frequency,
                notes,
                '[]'::jsonb
            FROM interventions
            WHERE NOT ({_POINT_EVENT_CONDITION})
            """
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM health_events"))
    op.execute(sa.text("DELETE FROM protocols"))
