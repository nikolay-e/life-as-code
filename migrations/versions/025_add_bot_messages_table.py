"""Add bot_messages table for Telegram bot conversation persistence

Revision ID: 025_bot_messages
Revises: 024_eight_sleep_source
Create Date: 2026-04-26

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "025_bot_messages"
down_revision: str | None = "024_eight_sleep_source"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "bot_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("chat_id", sa.BigInteger(), nullable=False, index=True),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", postgresql.JSONB(), nullable=False),
        sa.Column("text_preview", sa.Text(), nullable=True),
        sa.Column(
            "source",
            sa.String(length=50),
            nullable=False,
            server_default="chat",
        ),
        sa.Column("telegram_message_id", sa.BigInteger(), nullable=True),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("cache_creation_input_tokens", sa.Integer(), nullable=True),
        sa.Column("cache_read_input_tokens", sa.Integer(), nullable=True),
        sa.Column("stop_reason", sa.String(length=50), nullable=True),
        sa.Column("request_id", sa.String(length=100), nullable=True),
        sa.Column("cleared_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "role IN ('user', 'assistant', 'system')",
            name="valid_bot_message_role",
        ),
    )
    op.create_index(
        "idx_bot_message_user_chat_created",
        "bot_messages",
        ["user_id", "chat_id", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("idx_bot_message_user_chat_created", table_name="bot_messages")
    op.drop_table("bot_messages")
