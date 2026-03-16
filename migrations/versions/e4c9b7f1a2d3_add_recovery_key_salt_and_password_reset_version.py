"""add recovery key salt and password reset version

Revision ID: e4c9b7f1a2d3
Revises: d3a7f9c2b4e1
Create Date: 2026-03-16 22:10:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e4c9b7f1a2d3'
down_revision = 'd3a7f9c2b4e1'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('recovery_key_salt', sa.String(length=64), nullable=True))
        batch_op.add_column(
            sa.Column('password_reset_version', sa.Integer(), nullable=False, server_default='0')
        )

    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.alter_column('password_reset_version', server_default=None)


def downgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('password_reset_version')
        batch_op.drop_column('recovery_key_salt')
