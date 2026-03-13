"""make goal and finance user non nullable

Revision ID: 8a2d8f4d5c1b
Revises: 5f7c6d9b1a2e
Create Date: 2026-03-12 23:10:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = '8a2d8f4d5c1b'
down_revision = '5f7c6d9b1a2e'
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()

    finance_without_user = connection.execute(
        sa.text('SELECT COUNT(1) FROM finances WHERE user_id IS NULL')
    ).scalar()
    goals_without_user = connection.execute(
        sa.text('SELECT COUNT(1) FROM goals WHERE user_id IS NULL')
    ).scalar()

    if finance_without_user:
        raise RuntimeError(
            'Existem registros em finances sem user_id. Corrija os dados antes de aplicar a migração.'
        )
    if goals_without_user:
        raise RuntimeError(
            'Existem registros em goals sem user_id. Corrija os dados antes de aplicar a migração.'
        )

    with op.batch_alter_table('finances', schema=None) as batch_op:
        batch_op.alter_column('user_id', existing_type=sa.Integer(), nullable=False)

    with op.batch_alter_table('goals', schema=None) as batch_op:
        batch_op.alter_column('user_id', existing_type=sa.Integer(), nullable=False)


def downgrade():
    with op.batch_alter_table('goals', schema=None) as batch_op:
        batch_op.alter_column('user_id', existing_type=sa.Integer(), nullable=True)

    with op.batch_alter_table('finances', schema=None) as batch_op:
        batch_op.alter_column('user_id', existing_type=sa.Integer(), nullable=True)
