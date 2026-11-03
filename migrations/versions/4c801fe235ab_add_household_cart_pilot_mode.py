"""Add explicitly consented household cart mode and device verification.

Revision ID: 4c801fe235ab
Revises: 3b7d1a84502f
"""
from alembic import op
import sqlalchemy as sa
revision = '4c801fe235ab'
down_revision = '3b7d1a84502f'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('shop_login') as batch:
        batch.add_column(sa.Column('task_kind', sa.String(16), nullable=False, server_default='login'))
        batch.add_column(sa.Column('agent_report', sa.String(32), nullable=True))
        batch.add_column(sa.Column('device_verified_at', sa.DateTime(), nullable=True))
        batch.create_check_constraint('shop_login_task_kind', "task_kind IN ('login','cart')")


def downgrade():
    with op.batch_alter_table('shop_login') as batch:
        batch.drop_constraint('shop_login_task_kind', type_='check')
        batch.drop_column('device_verified_at')
        batch.drop_column('agent_report')
        batch.drop_column('task_kind')
