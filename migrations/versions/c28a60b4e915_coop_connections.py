"""Separate saved shop profiles and confirm exact offers without replacing data."""
from alembic import op
import sqlalchemy as sa

revision = 'c28a60b4e915'
down_revision = 'a47b9d31e602'
branch_labels = None
depends_on = None


def upgrade():
    legacy_unique = next(c['name'] for c in sa.inspect(op.get_bind()).get_unique_constraints('shop_browser')
                         if c['column_names'] == ['household_id'])
    # Name the legacy anonymous unique constraint for SQLite batch reflection.
    with op.batch_alter_table('shop_browser', naming_convention={
            'uq': 'uq_%(table_name)s_%(column_0_name)s'}) as batch:
        batch.add_column(sa.Column('shop_key', sa.String(16), nullable=False, server_default='galaxus'))
        batch.drop_constraint(legacy_unique or 'uq_shop_browser_household_id', type_='unique')
        batch.create_unique_constraint('browser_household_shop', ['household_id', 'shop_key'])
        batch.create_check_constraint('browser_shop_key', "shop_key IN ('coop','galaxus')")
    # Add in place: purchase_source is referenced by existing offers and plans.
    op.add_column('purchase_source', sa.Column('shop_key', sa.String(16),
        sa.CheckConstraint("shop_key IS NULL OR shop_key IN ('coop','galaxus')", name='source_shop_key')))
    op.create_index('source_household_shop', 'purchase_source', ['household_id', 'shop_key'], unique=True)
    # Only canonical existing names; aliases or custom names need explicit binding.
    op.execute("UPDATE purchase_source SET shop_key=name_key, version=version+1 WHERE name_key IN ('coop','galaxus')")
    op.add_column('shop_offer', sa.Column('confirmed_signature', sa.String(64)))
    op.add_column('shop_offer', sa.Column('confirmed_at', sa.DateTime()))


def downgrade():
    # Never discard a saved Coop login during a downgrade.
    if op.get_bind().execute(sa.text("SELECT COUNT(*) FROM shop_browser WHERE shop_key != 'galaxus'")).scalar():
        raise RuntimeError('Remove Coop connections explicitly before downgrading.')
    op.drop_column('shop_offer', 'confirmed_at')
    op.drop_column('shop_offer', 'confirmed_signature')
    op.drop_index('source_household_shop', table_name='purchase_source')
    if op.get_bind().dialect.name != 'sqlite':
        op.drop_constraint('source_shop_key', 'purchase_source', type_='check')
    op.drop_column('purchase_source', 'shop_key')
    with op.batch_alter_table('shop_browser') as batch:
        batch.drop_constraint('browser_shop_key', type_='check')
        batch.drop_constraint('browser_household_shop', type_='unique')
        batch.drop_column('shop_key')
        batch.create_unique_constraint('uq_shop_browser_household_id', ['household_id'])
