"""add username change cooldown

Revision ID: c9e7a4d2b6f1
Revises: a7d4e2c9f1b6
Create Date: 2026-07-13 15:10:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = 'c9e7a4d2b6f1'
down_revision = 'a7d4e2c9f1b6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('username_changed_at', sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('username_changed_at')
