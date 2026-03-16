"""add foundation schema for v130

Revision ID: b1f0d3c4a5e6
Revises: 8a2d8f4d5c1b
Create Date: 2026-03-15 10:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = 'b1f0d3c4a5e6'
down_revision = '8a2d8f4d5c1b'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('recovery_key_version', sa.Integer(), nullable=False, server_default='1'))
        batch_op.add_column(sa.Column('recovery_key_generated_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('recovery_key_last_sent_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('last_login_at', sa.DateTime(), nullable=True))

    with op.batch_alter_table('finances', schema=None) as batch_op:
        batch_op.add_column(sa.Column('subcategory', sa.String(length=80), nullable=True))
        batch_op.add_column(sa.Column('payment_method', sa.String(length=40), nullable=True))

    with op.batch_alter_table('recurring_entries', schema=None) as batch_op:
        batch_op.add_column(sa.Column('subcategory', sa.String(length=80), nullable=True))
        batch_op.add_column(sa.Column('payment_method', sa.String(length=40), nullable=True))

    op.create_table(
        'backup_schedules',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('frequency', sa.String(length=20), nullable=False, server_default='Semanal'),
        sa.Column('times_per_period', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('day_of_week', sa.Integer(), nullable=True),
        sa.Column('day_of_month', sa.Integer(), nullable=True),
        sa.Column('run_hour', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('run_minute', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('retention_count', sa.Integer(), nullable=False, server_default='20'),
        sa.Column('last_run_at', sa.DateTime(), nullable=True),
        sa.Column('next_run_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', name='uq_backup_schedule_user'),
    )
    op.create_index('ix_backup_schedule_enabled_next_run', 'backup_schedules', ['enabled', 'next_run_at'], unique=False)

    op.create_table(
        'backup_records',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('schedule_id', sa.Integer(), nullable=True),
        sa.Column('trigger_source', sa.String(length=20), nullable=False, server_default='Manual'),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='Concluido'),
        sa.Column('file_name', sa.String(length=255), nullable=False),
        sa.Column('storage_path', sa.String(length=512), nullable=False),
        sa.Column('file_size_bytes', sa.BigInteger(), nullable=True),
        sa.Column('checksum', sa.String(length=128), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['schedule_id'], ['backup_schedules.id']),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_backup_records_user_created_at', 'backup_records', ['user_id', 'created_at'], unique=False)
    op.create_index('ix_backup_records_schedule_created_at', 'backup_records', ['schedule_id', 'created_at'], unique=False)
    op.create_index('ix_backup_records_status_created_at', 'backup_records', ['status', 'created_at'], unique=False)

    op.create_table(
        'user_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('session_token_hash', sa.String(length=128), nullable=False),
        sa.Column('ip_address', sa.String(length=64), nullable=True),
        sa.Column('user_agent', sa.String(length=255), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(), nullable=False),
        sa.Column('ended_at', sa.DateTime(), nullable=True),
        sa.Column('ended_reason', sa.String(length=40), nullable=True),
        sa.Column('is_current', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('session_token_hash'),
    )
    op.create_index('ix_user_sessions_user_started_at', 'user_sessions', ['user_id', 'started_at'], unique=False)
    op.create_index('ix_user_sessions_user_is_current', 'user_sessions', ['user_id', 'is_current'], unique=False)

    op.create_table(
        'activity_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('event_category', sa.String(length=40), nullable=False),
        sa.Column('event_type', sa.String(length=64), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('details_json', sa.Text(), nullable=True),
        sa.Column('ip_address', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_activity_logs_user_created_at', 'activity_logs', ['user_id', 'created_at'], unique=False)
    op.create_index('ix_activity_logs_category_created_at', 'activity_logs', ['event_category', 'created_at'], unique=False)

    op.create_table(
        'system_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('severity', sa.String(length=20), nullable=False, server_default='info'),
        sa.Column('source', sa.String(length=50), nullable=False),
        sa.Column('event_code', sa.String(length=80), nullable=True),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('details_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_system_events_severity_created_at', 'system_events', ['severity', 'created_at'], unique=False)
    op.create_index('ix_system_events_source_created_at', 'system_events', ['source', 'created_at'], unique=False)
    op.create_index('ix_system_events_user_created_at', 'system_events', ['user_id', 'created_at'], unique=False)

    op.create_table(
        'app_update_state',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('installed_version', sa.String(length=32), nullable=False),
        sa.Column('latest_known_version', sa.String(length=32), nullable=True),
        sa.Column('update_channel', sa.String(length=20), nullable=False, server_default='stable'),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='idle'),
        sa.Column('last_checked_at', sa.DateTime(), nullable=True),
        sa.Column('last_downloaded_at', sa.DateTime(), nullable=True),
        sa.Column('downloaded_asset_path', sa.String(length=512), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_app_update_state_last_checked_at', 'app_update_state', ['last_checked_at'], unique=False)

    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.alter_column('recovery_key_version', server_default=None)


def downgrade():
    op.drop_index('ix_app_update_state_last_checked_at', table_name='app_update_state')
    op.drop_table('app_update_state')

    op.drop_index('ix_system_events_user_created_at', table_name='system_events')
    op.drop_index('ix_system_events_source_created_at', table_name='system_events')
    op.drop_index('ix_system_events_severity_created_at', table_name='system_events')
    op.drop_table('system_events')

    op.drop_index('ix_activity_logs_category_created_at', table_name='activity_logs')
    op.drop_index('ix_activity_logs_user_created_at', table_name='activity_logs')
    op.drop_table('activity_logs')

    op.drop_index('ix_user_sessions_user_is_current', table_name='user_sessions')
    op.drop_index('ix_user_sessions_user_started_at', table_name='user_sessions')
    op.drop_table('user_sessions')

    op.drop_index('ix_backup_records_status_created_at', table_name='backup_records')
    op.drop_index('ix_backup_records_schedule_created_at', table_name='backup_records')
    op.drop_index('ix_backup_records_user_created_at', table_name='backup_records')
    op.drop_table('backup_records')

    op.drop_index('ix_backup_schedule_enabled_next_run', table_name='backup_schedules')
    op.drop_table('backup_schedules')

    with op.batch_alter_table('recurring_entries', schema=None) as batch_op:
        batch_op.drop_column('payment_method')
        batch_op.drop_column('subcategory')

    with op.batch_alter_table('finances', schema=None) as batch_op:
        batch_op.drop_column('payment_method')
        batch_op.drop_column('subcategory')

    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('last_login_at')
        batch_op.drop_column('recovery_key_last_sent_at')
        batch_op.drop_column('recovery_key_generated_at')
        batch_op.drop_column('recovery_key_version')
