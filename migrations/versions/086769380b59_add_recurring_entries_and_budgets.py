"""Add recurring entries and budgets

Revision ID: 086769380b59
Revises: 1ef0e9d8a490
Create Date: 2026-02-11 02:47:35.290458

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '086769380b59'
down_revision = '1ef0e9d8a490'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('budgets',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('category', sa.String(length=50), nullable=False),
    sa.Column('limit_amount', sa.Float(), nullable=False),
    sa.Column('period', sa.String(length=20), nullable=True),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], name=op.f('fk_budgets_user_id_user')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_budgets')),
    sa.UniqueConstraint('user_id', 'category', 'period', name='uq_budget_user_category_period'),
    )
    op.create_index('ix_budgets_user_period', 'budgets', ['user_id', 'period'], unique=False)
    op.create_table('recurring_entries',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('description', sa.String(length=100), nullable=False),
    sa.Column('value', sa.Float(), nullable=False),
    sa.Column('category', sa.String(length=50), nullable=False),
    sa.Column('type', sa.String(length=20), nullable=False),
    sa.Column('frequency', sa.String(length=20), nullable=False),
    sa.Column('start_date', sa.Date(), nullable=False),
    sa.Column('end_date', sa.Date(), nullable=True),
    sa.Column('next_run_date', sa.Date(), nullable=False),
    sa.Column('last_run_date', sa.Date(), nullable=True),
    sa.Column('active', sa.Boolean(), nullable=True),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], name=op.f('fk_recurring_entries_user_id_user')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_recurring_entries'))
    )
    op.create_index(
        'ix_recurring_user_next_run_active',
        'recurring_entries',
        ['user_id', 'next_run_date', 'active'],
        unique=False,
    )


def downgrade():
    op.drop_index('ix_recurring_user_next_run_active', table_name='recurring_entries')
    op.drop_table('recurring_entries')
    op.drop_index('ix_budgets_user_period', table_name='budgets')
    op.drop_table('budgets')
