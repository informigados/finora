"""add recovery key ciphertext and mail support

Revision ID: d3a7f9c2b4e1
Revises: b1f0d3c4a5e6
Create Date: 2026-03-15 20:10:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd3a7f9c2b4e1'
down_revision = 'b1f0d3c4a5e6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('recovery_key_ciphertext', sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('recovery_key_ciphertext')
