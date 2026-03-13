"""Add login lockout fields to user

Revision ID: 5f7c6d9b1a2e
Revises: c7f6a8a31d10
Create Date: 2026-03-12 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5f7c6d9b1a2e'
down_revision = 'c7f6a8a31d10'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {column['name'] for column in inspector.get_columns('user')}

    with op.batch_alter_table('user', schema=None) as batch_op:
        if 'failed_login_attempts' not in existing_columns:
            batch_op.add_column(
                sa.Column('failed_login_attempts', sa.Integer(), nullable=False, server_default='0')
            )
        if 'locked_until' not in existing_columns:
            batch_op.add_column(
                sa.Column('locked_until', sa.DateTime(), nullable=True)
            )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {column['name'] for column in inspector.get_columns('user')}

    with op.batch_alter_table('user', schema=None) as batch_op:
        if 'locked_until' in existing_columns:
            batch_op.drop_column('locked_until')
        if 'failed_login_attempts' in existing_columns:
            batch_op.drop_column('failed_login_attempts')
