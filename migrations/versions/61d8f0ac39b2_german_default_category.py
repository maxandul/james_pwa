"""Correct the built-in German category label without replacing category IDs.

Revision ID: 61d8f0ac39b2
Revises: 5d9a21f067ce
"""
from alembic import op
import sqlalchemy as sa

revision = '61d8f0ac39b2'
down_revision = '5d9a21f067ce'
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    category = sa.table('category', sa.column('id', sa.Integer), sa.column('household_id', sa.Integer),
        sa.column('name', sa.String), sa.column('name_key', sa.String), sa.column('aliases', sa.JSON),
        sa.column('version', sa.Integer))
    item = sa.table('household_item', sa.column('household_id', sa.Integer),
        sa.column('category', sa.String), sa.column('version', sa.Integer))
    household = sa.table('household', sa.column('id', sa.Integer),
        sa.column('settings', sa.JSON), sa.column('version', sa.Integer))
    legacy = connection.execute(sa.select(category).where(category.c.name == 'Getraenke',
        category.c.name_key == 'getraenke')).mappings().all()
    for entry in legacy:
        others = connection.execute(sa.select(category.c.name_key, category.c.aliases).where(
            category.c.household_id == entry['household_id'], category.c.id != entry['id'])).mappings()
        taken = {name for record in others for name in [record['name_key'], *(record['aliases'] or [])]}
        name = 'Getränke'
        # Preserve distinct, user-created groups instead of silently merging them.
        suffix = 1
        while name.casefold() in taken:
            name = f'Getränke (bisher {suffix})'
            suffix += 1
        aliases = sorted(set(entry['aliases'] or []) | {'getraenke'})
        connection.execute(category.update().where(category.c.id == entry['id']).values(
            name=name, name_key=name.casefold(), aliases=aliases, version=category.c.version + 1))
        connection.execute(item.update().where(item.c.household_id == entry['household_id'],
            item.c.category == 'Getraenke').values(category=name, version=item.c.version + 1))
    # A previously renamed default must not reappear as an additional category.
    records = connection.execute(sa.select(category)).mappings().all()
    for entry in records:
        aliases = set(entry['aliases'] or [])
        if 'getraenke' not in aliases or entry['name_key'] == 'getränke' or 'getränke' in aliases:
            continue
        other = any(record['household_id'] == entry['household_id'] and
            record['id'] != entry['id'] and (record['name_key'] == 'getränke' or
                'getränke' in (record['aliases'] or [])) for record in records)
        if not other:
            connection.execute(category.update().where(category.c.id == entry['id']).values(
                aliases=sorted(aliases | {'getränke'}), version=category.c.version + 1))
    # Deleted defaults and explicit replacement mappings keep their meaning.
    for home in connection.execute(sa.select(household)).mappings().all():
        settings = dict(home['settings'] or {})
        deleted = list(settings.get('catalogue_deleted', []))
        redirects = dict(settings.get('catalogue_redirects', {}))
        changed = False
        if 'category:getraenke' in deleted and 'category:getränke' not in deleted:
            settings['catalogue_deleted'] = sorted(set(deleted) | {'category:getränke'})
            changed = True
        if 'category:getraenke' in redirects and 'category:getränke' not in redirects:
            redirects['category:getränke'] = redirects['category:getraenke']
            settings['catalogue_redirects'] = redirects
            changed = True
        if changed:
            connection.execute(household.update().where(household.c.id == home['id']).values(
                settings=settings, version=household.c.version + 1))


def downgrade():
    # A spelling correction is intentionally retained; IDs and schema are unchanged.
    pass
