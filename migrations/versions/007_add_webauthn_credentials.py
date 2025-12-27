"""Add WebAuthn credentials support

Revision ID: 007_add_webauthn_credentials
Revises: 006_add_google_source
Create Date: 2024-12-24

This migration adds:
1. webauthn_credentials table for storing passkey credentials
2. has_passkey column to users table
3. passkey_required_at column to users table for time-based passkey enforcement
"""

import sqlalchemy as sa
from alembic import op

revision = "007_add_webauthn_credentials"
down_revision = "006_add_google_source"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "webauthn_credentials",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("credential_id", sa.Text(), nullable=False),
        sa.Column("credential_public_key", sa.Text(), nullable=False),
        sa.Column("sign_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("transports", sa.Text(), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_webauthn_credentials_user_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_webauthn_credentials"),
        sa.UniqueConstraint("credential_id", name="uq_webauthn_credential_id"),
    )

    op.create_index(
        "idx_webauthn_credentials_user_id",
        "webauthn_credentials",
        ["user_id"],
        unique=False,
    )

    op.create_index(
        "idx_webauthn_credentials_credential_id",
        "webauthn_credentials",
        ["credential_id"],
        unique=True,
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'users' AND column_name = 'has_passkey'
            ) THEN
                ALTER TABLE users ADD COLUMN has_passkey BOOLEAN NOT NULL DEFAULT FALSE;
            END IF;
        END$$;
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'users' AND column_name = 'passkey_required_at'
            ) THEN
                ALTER TABLE users ADD COLUMN passkey_required_at TIMESTAMP NULL;
            END IF;
        END$$;
        """
    )


def downgrade():
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'users' AND column_name = 'passkey_required_at'
            ) THEN
                ALTER TABLE users DROP COLUMN passkey_required_at;
            END IF;
        END$$;
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'users' AND column_name = 'has_passkey'
            ) THEN
                ALTER TABLE users DROP COLUMN has_passkey;
            END IF;
        END$$;
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            DROP INDEX IF EXISTS idx_webauthn_credentials_credential_id;
        EXCEPTION
            WHEN undefined_object THEN NULL;
        END$$;
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            DROP INDEX IF EXISTS idx_webauthn_credentials_user_id;
        EXCEPTION
            WHEN undefined_object THEN NULL;
        END$$;
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            DROP TABLE IF EXISTS webauthn_credentials CASCADE;
        EXCEPTION
            WHEN undefined_object THEN NULL;
        END$$;
        """
    )
