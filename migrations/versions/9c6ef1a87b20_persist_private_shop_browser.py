"""Persist private household browser references.

Revision ID: 9c6ef1a87b20
Revises: 7a4224e5e7e4
"""
from alembic import op
import sqlalchemy as sa

revision = '9c6ef1a87b20'
down_revision = '7a4224e5e7e4'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('shop_browser',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('household_id', sa.Integer(), sa.ForeignKey('household.id'), nullable=False, unique=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('auth_version', sa.Integer(), nullable=False),
        sa.Column('state', sa.String(24), nullable=False),
        sa.Column('context_id', sa.String(128)),
        sa.Column('session_id', sa.String(128)),
        sa.Column('live_url', sa.Text()),
        sa.Column('expires_at', sa.DateTime()),
        sa.Column('confirmed_at', sa.DateTime()),
        sa.Column('error_category', sa.String(32)),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.CheckConstraint("state IN ('idle','queued','creating','active','closing','forgetting','error')", name='shop_browser_state'))


def downgrade():
    op.drop_table('shop_browser')
