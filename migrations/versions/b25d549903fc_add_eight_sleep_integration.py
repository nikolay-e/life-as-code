"""Add Eight Sleep integration

Revision ID: b25d549903fc
Revises: 023_sync_backoff
Create Date: 2026-04-18 09:24:00.191274

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'b25d549903fc'  # pragma: allowlist secret
down_revision: Union[str, None] = '023_sync_backoff'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('eight_sleep_sessions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('date', sa.Date(), nullable=False),
    sa.Column('source', sa.String(length=50), nullable=False),
    sa.Column('score', sa.Integer(), nullable=True),
    sa.Column('sleep_duration_seconds', sa.Integer(), nullable=True),
    sa.Column('light_duration_seconds', sa.Integer(), nullable=True),
    sa.Column('deep_duration_seconds', sa.Integer(), nullable=True),
    sa.Column('rem_duration_seconds', sa.Integer(), nullable=True),
    sa.Column('tnt', sa.Integer(), nullable=True),
    sa.Column('heart_rate', sa.Float(), nullable=True),
    sa.Column('hrv', sa.Float(), nullable=True),
    sa.Column('respiratory_rate', sa.Float(), nullable=True),
    sa.Column('latency_asleep_seconds', sa.Integer(), nullable=True),
    sa.Column('latency_out_seconds', sa.Integer(), nullable=True),
    sa.Column('bed_temp_celsius', sa.Float(), nullable=True),
    sa.Column('room_temp_celsius', sa.Float(), nullable=True),
    sa.Column('sleep_fitness_score', sa.Integer(), nullable=True),
    sa.Column('sleep_routine_score', sa.Integer(), nullable=True),
    sa.Column('sleep_quality_score', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.CheckConstraint('(heart_rate >= 20 AND heart_rate <= 250) OR heart_rate IS NULL', name='valid_eight_sleep_hr'),
    sa.CheckConstraint('(hrv >= 0 AND hrv <= 500) OR hrv IS NULL', name='valid_eight_sleep_hrv'),
    sa.CheckConstraint('(respiratory_rate >= 5 AND respiratory_rate <= 50) OR respiratory_rate IS NULL', name='valid_eight_sleep_resp_rate'),
    sa.CheckConstraint('(score >= 0 AND score <= 100) OR score IS NULL', name='valid_eight_sleep_score'),
    sa.CheckConstraint('(sleep_duration_seconds >= 0) OR sleep_duration_seconds IS NULL', name='valid_eight_sleep_duration'),
    sa.CheckConstraint('(sleep_fitness_score >= 0 AND sleep_fitness_score <= 100) OR sleep_fitness_score IS NULL', name='valid_eight_sleep_fitness_score'),
    sa.CheckConstraint('(sleep_quality_score >= 0 AND sleep_quality_score <= 100) OR sleep_quality_score IS NULL', name='valid_eight_sleep_quality_score'),
    sa.CheckConstraint('(sleep_routine_score >= 0 AND sleep_routine_score <= 100) OR sleep_routine_score IS NULL', name='valid_eight_sleep_routine_score'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'date', 'source', name='_user_eight_sleep_date_source_uc')
    )
    op.create_index('idx_eight_sleep_user_date', 'eight_sleep_sessions', ['user_id', sa.text('date DESC')], unique=False)

    with op.batch_alter_table('user_credentials', schema=None) as batch_op:
        batch_op.add_column(sa.Column('eight_sleep_email', sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column('encrypted_eight_sleep_password', sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column('encrypted_eight_sleep_access_token', sa.String(length=1000), nullable=True))
        batch_op.add_column(sa.Column('eight_sleep_token_expires_at', sa.DateTime(), nullable=True))

    op.drop_constraint('valid_sync_source', 'data_sync', type_='check')
    op.create_check_constraint(
        'valid_sync_source', 'data_sync',
        "source IN ('garmin', 'hevy', 'whoop', 'google', 'apple_health', 'eight_sleep')"
    )


def downgrade() -> None:
    with op.batch_alter_table('user_credentials', schema=None) as batch_op:
        batch_op.drop_column('eight_sleep_token_expires_at')
        batch_op.drop_column('encrypted_eight_sleep_access_token')
        batch_op.drop_column('encrypted_eight_sleep_password')
        batch_op.drop_column('eight_sleep_email')

    op.drop_index('idx_eight_sleep_user_date', table_name='eight_sleep_sessions')
    op.drop_table('eight_sleep_sessions')
