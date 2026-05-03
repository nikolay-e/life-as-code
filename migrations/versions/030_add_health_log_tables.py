"""Add health_events, protocols, health_notes tables

Revision ID: 030_add_health_log_tables
Revises: 029_wset_tmpl_id
Create Date: 2026-05-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "030_add_health_log_tables"
down_revision: str | None = "029_wset_tmpl_id"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # protocols must be created BEFORE health_events (FK dependency)
    op.create_table(
        "protocols",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("domain", sa.String(50), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date()),
        sa.Column("dosage", sa.Text()),
        sa.Column("frequency", sa.Text()),
        sa.Column("notes", sa.Text()),
        sa.Column(
            "tags",
            JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "domain IN ('supplement','medication','diet','lifestyle','training','other')",
            name="valid_protocol_domain",
        ),
        sa.CheckConstraint(
            "end_date IS NULL OR end_date >= start_date",
            name="valid_protocol_dates",
        ),
    )
    op.create_index("idx_protocol_user_start", "protocols", ["user_id", "start_date"])
    op.create_index("idx_protocol_user_active", "protocols", ["user_id", "end_date"])

    op.create_table(
        "health_events",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("domain", sa.String(50), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "start_ts",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("end_ts", sa.DateTime(timezone=True)),
        sa.Column("dosage", sa.Text()),
        sa.Column("notes", sa.Text()),
        sa.Column(
            "attributes",
            JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "tags",
            JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "protocol_id",
            sa.BigInteger(),
            sa.ForeignKey("protocols.id", ondelete="SET NULL"),
        ),
        sa.CheckConstraint(
            "domain IN ('substance','therapy','nutrition','sleep','stress','environment','symptom','medication')",
            name="valid_health_event_domain",
        ),
        sa.CheckConstraint(
            "end_ts IS NULL OR end_ts > start_ts",
            name="valid_health_event_duration",
        ),
    )
    op.create_index(
        "idx_health_event_user_start", "health_events", ["user_id", "start_ts"]
    )

    op.create_table(
        "health_notes",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "attributes",
            JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "tags",
            JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index(
        "idx_health_note_user_created", "health_notes", ["user_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("idx_health_note_user_created", table_name="health_notes")
    op.drop_table("health_notes")

    op.drop_index("idx_health_event_user_start", table_name="health_events")
    op.drop_table("health_events")

    op.drop_index("idx_protocol_user_active", table_name="protocols")
    op.drop_index("idx_protocol_user_start", table_name="protocols")
    op.drop_table("protocols")
