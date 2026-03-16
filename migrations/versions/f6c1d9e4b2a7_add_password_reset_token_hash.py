"""add password reset token hash

Revision ID: f6c1d9e4b2a7
Revises: e4c9b7f1a2d3
Create Date: 2026-03-16 23:40:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f6c1d9e4b2a7'
down_revision = 'e4c9b7f1a2d3'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('password_reset_token_hash', sa.String(length=64), nullable=True))


def downgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('password_reset_token_hash')
