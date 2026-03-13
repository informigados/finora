"""Add session timeout to user

Revision ID: c7f6a8a31d10
Revises: 086769380b59
Create Date: 2026-03-02 11:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c7f6a8a31d10'
down_revision = '086769380b59'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {column['name'] for column in inspector.get_columns('user')}

    if 'session_timeout_minutes' in existing_columns:
        return

    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('session_timeout_minutes', sa.Integer(), nullable=False, server_default='0')
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {column['name'] for column in inspector.get_columns('user')}

    if 'session_timeout_minutes' not in existing_columns:
        return

    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('session_timeout_minutes')
