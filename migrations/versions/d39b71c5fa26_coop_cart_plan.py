"""Link a bounded browser cart job to the existing exact purchase plan."""
from alembic import op
import sqlalchemy as sa

revision = 'd39b71c5fa26'
down_revision = 'c28a60b4e915'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('purchase_plan', sa.Column('cart_state', sa.String(32)))
    op.add_column('purchase_plan', sa.Column('cart_requested_at', sa.DateTime()))
    op.add_column('purchase_plan', sa.Column('cart_actions', sa.Integer(), nullable=False, server_default='0'))
    with op.batch_alter_table('shop_browser') as batch:
        batch.add_column(sa.Column('cart_plan_id', sa.Integer()))
        batch.create_foreign_key('browser_cart_plan', 'purchase_plan', ['cart_plan_id'], ['id'])


def downgrade():
    with op.batch_alter_table('shop_browser') as batch:
        batch.drop_constraint('browser_cart_plan', type_='foreignkey')
        batch.drop_column('cart_plan_id')
    op.drop_column('purchase_plan', 'cart_actions')
    op.drop_column('purchase_plan', 'cart_requested_at')
    op.drop_column('purchase_plan', 'cart_state')
