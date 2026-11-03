"""Add household administration, catalogue lifecycle and saved shopping views.

Revision ID: 5d9a21f067ce
Revises: 4c801fe235ab
"""
from alembic import op
import sqlalchemy as sa

revision = '5d9a21f067ce'
down_revision = '4c801fe235ab'
branch_labels = None
depends_on = None


def upgrade():
    # Additive only: all previous accounts, memberships, articles and history remain.
    for table, json_field in [('household', 'settings'), ('user', 'preferences')]:
        op.add_column(table, sa.Column(json_field, sa.JSON(), nullable=False, server_default=sa.text("'{}'")))
        op.add_column(table, sa.Column('version', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('membership', sa.Column('version', sa.Integer(), nullable=False, server_default='1'))
    for table in ('category', 'purchase_source'):
        op.add_column(table, sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.create_table('shopping_view',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('household_id', sa.Integer(), sa.ForeignKey('household.id'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=True),
        sa.Column('source_id', sa.Integer(), sa.ForeignKey('purchase_source.id'), nullable=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('category_ids', sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column('category_order', sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column('item_sort', sa.String(20), nullable=False, server_default='name'),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.CheckConstraint("item_sort IN ('name','name_desc','favorites')", name='shopping_view_sort'))
    op.create_index('ix_shopping_view_household_id', 'shopping_view', ['household_id'])
    op.create_index('ix_shopping_view_user_id', 'shopping_view', ['user_id'])


def downgrade():
    op.drop_index('ix_shopping_view_user_id', table_name='shopping_view')
    op.drop_index('ix_shopping_view_household_id', table_name='shopping_view')
    op.drop_table('shopping_view')
    for table in ('category', 'purchase_source'):
        op.drop_column(table, 'active')
    op.drop_column('membership', 'version')
    for table, json_field in [('user', 'preferences'), ('household', 'settings')]:
        op.drop_column(table, 'version')
        op.drop_column(table, json_field)
