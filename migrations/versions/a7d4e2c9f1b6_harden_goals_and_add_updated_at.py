"""Harden goals and add updated_at

Revision ID: a7d4e2c9f1b6
Revises: f6c1d9e4b2a7
Create Date: 2026-03-16 02:55:00
"""

from alembic import op
import sqlalchemy as sa


revision = 'a7d4e2c9f1b6'
down_revision = 'f6c1d9e4b2a7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('goals', schema=None) as batch_op:
        batch_op.add_column(sa.Column('updated_at', sa.DateTime(), nullable=True))
        batch_op.create_check_constraint(
            'ck_goals_target_amount_positive',
            'target_amount > 0',
        )
        batch_op.create_check_constraint(
            'ck_goals_current_amount_non_negative',
            'current_amount >= 0',
        )


def downgrade():
    with op.batch_alter_table('goals', schema=None) as batch_op:
        batch_op.drop_constraint('ck_goals_current_amount_non_negative', type_='check')
        batch_op.drop_constraint('ck_goals_target_amount_positive', type_='check')
        batch_op.drop_column('updated_at')
