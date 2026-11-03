"""Retain safe login outcomes independently of session cleanup.

Revision ID: 3b7d1a84502f
Revises: 2a8c10657d20
"""
from alembic import op
import sqlalchemy as sa

revision = '3b7d1a84502f'
down_revision = '2a8c10657d20'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('shop_login') as batch:
        batch.add_column(sa.Column('outcome', sa.String(32), nullable=True))
        batch.add_column(sa.Column('error_category', sa.String(32), nullable=True))
        batch.add_column(sa.Column('http_status', sa.Integer(), nullable=True))
        batch.add_column(sa.Column('browser_calls', sa.Integer(), nullable=True))
        batch.add_column(sa.Column('auth_progress', sa.String(24), nullable=True))


def downgrade():
    with op.batch_alter_table('shop_login') as batch:
        for column in ('auth_progress', 'browser_calls', 'http_status', 'error_category', 'outcome'):
            batch.drop_column(column)
