"""add accounts and reconciliation for v144

Revision ID: f4a8c2d7e1b9
Revises: c9e7a4d2b6f1
Create Date: 2026-07-20 19:10:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = 'f4a8c2d7e1b9'
down_revision = 'c9e7a4d2b6f1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'financial_accounts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=80), nullable=False),
        sa.Column('account_type', sa.String(length=24), nullable=False, server_default='checking'),
        sa.Column('institution', sa.String(length=100), nullable=True),
        sa.Column('last_four', sa.String(length=4), nullable=True),
        sa.Column('color', sa.String(length=7), nullable=False, server_default='#2563EB'),
        sa.Column('initial_balance', sa.Numeric(precision=14, scale=2), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'name', name='uq_financial_account_user_name'),
    )
    op.create_index(
        'ix_financial_accounts_user_active',
        'financial_accounts',
        ['user_id', 'is_active'],
        unique=False,
    )

    with op.batch_alter_table('finances', schema=None) as batch_op:
        batch_op.add_column(sa.Column('account_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_finances_account_id_financial_accounts',
            'financial_accounts',
            ['account_id'],
            ['id'],
        )
        batch_op.create_index('ix_finances_user_account', ['user_id', 'account_id'], unique=False)

    with op.batch_alter_table('recurring_entries', schema=None) as batch_op:
        batch_op.add_column(sa.Column('account_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_recurring_entries_account_id_financial_accounts',
            'financial_accounts',
            ['account_id'],
            ['id'],
        )

    op.create_table(
        'account_transfers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('source_account_id', sa.Integer(), nullable=False),
        sa.Column('destination_account_id', sa.Integer(), nullable=False),
        sa.Column('amount', sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column('transfer_date', sa.Date(), nullable=False),
        sa.Column('description', sa.String(length=140), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint('amount > 0', name='ck_transfer_positive_amount'),
        sa.CheckConstraint('source_account_id <> destination_account_id', name='ck_transfer_distinct_accounts'),
        sa.ForeignKeyConstraint(['destination_account_id'], ['financial_accounts.id']),
        sa.ForeignKeyConstraint(['source_account_id'], ['financial_accounts.id']),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_account_transfers_user_date',
        'account_transfers',
        ['user_id', 'transfer_date'],
        unique=False,
    )

    op.create_table(
        'bank_import_profiles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(length=80), nullable=False),
        sa.Column('file_type', sa.String(length=8), nullable=False),
        sa.Column('delimiter', sa.String(length=4), nullable=True),
        sa.Column('mapping_json', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['account_id'], ['financial_accounts.id']),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'name', name='uq_bank_import_profile_user_name'),
    )
    op.create_index(
        'ix_bank_import_profiles_user_account',
        'bank_import_profiles',
        ['user_id', 'account_id'],
        unique=False,
    )

    op.create_table(
        'bank_transactions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('external_id', sa.String(length=140), nullable=True),
        sa.Column('fingerprint', sa.String(length=64), nullable=False),
        sa.Column('transaction_date', sa.Date(), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=False),
        sa.Column('amount', sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column('source', sa.String(length=16), nullable=False, server_default='ofx'),
        sa.Column('reconciled_finance_id', sa.Integer(), nullable=True),
        sa.Column('reconciled_at', sa.DateTime(), nullable=True),
        sa.Column('imported_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['account_id'], ['financial_accounts.id']),
        sa.ForeignKeyConstraint(['reconciled_finance_id'], ['finances.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('account_id', 'fingerprint', name='uq_bank_transaction_account_fingerprint'),
    )
    op.create_index(
        'ix_bank_transactions_account_reconciled',
        'bank_transactions',
        ['account_id', 'reconciled_finance_id'],
        unique=False,
    )
    op.create_index(
        'ix_bank_transactions_user_date',
        'bank_transactions',
        ['user_id', 'transaction_date'],
        unique=False,
    )


def downgrade():
    op.drop_index('ix_bank_transactions_user_date', table_name='bank_transactions')
    op.drop_index('ix_bank_transactions_account_reconciled', table_name='bank_transactions')
    op.drop_table('bank_transactions')
    op.drop_index('ix_bank_import_profiles_user_account', table_name='bank_import_profiles')
    op.drop_table('bank_import_profiles')
    op.drop_index('ix_account_transfers_user_date', table_name='account_transfers')
    op.drop_table('account_transfers')

    with op.batch_alter_table('finances', schema=None) as batch_op:
        batch_op.drop_index('ix_finances_user_account')
        batch_op.drop_constraint('fk_finances_account_id_financial_accounts', type_='foreignkey')
        batch_op.drop_column('account_id')

    with op.batch_alter_table('recurring_entries', schema=None) as batch_op:
        batch_op.drop_constraint('fk_recurring_entries_account_id_financial_accounts', type_='foreignkey')
        batch_op.drop_column('account_id')

    op.drop_index('ix_financial_accounts_user_active', table_name='financial_accounts')
    op.drop_table('financial_accounts')
