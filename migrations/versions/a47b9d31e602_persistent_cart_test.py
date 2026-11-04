"""Bounded cart test on the existing private browser."""
from alembic import op
import sqlalchemy as sa

revision = 'a47b9d31e602'
down_revision = '8e26a1c490bf'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('shop_browser', sa.Column('cart_state', sa.String(32)))
    op.add_column('shop_browser', sa.Column('cart_actions', sa.Integer(), nullable=False, server_default='0'))


def downgrade():
    op.drop_column('shop_browser', 'cart_actions')
    op.drop_column('shop_browser', 'cart_state')
