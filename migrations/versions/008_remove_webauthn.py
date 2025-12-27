"""Remove WebAuthn/Passkey feature entirely

Revision ID: 008_remove_webauthn
Revises: 007_add_webauthn_credentials
Create Date: 2024-12-27

This migration removes:
1. webauthn_credentials table
2. has_passkey column from users table
3. passkey_required_at column from users table
"""

from alembic import op

revision = "008_remove_webauthn"
down_revision = "007_add_webauthn_credentials"
branch_labels = None
depends_on = None


def upgrade():
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


def downgrade():
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
