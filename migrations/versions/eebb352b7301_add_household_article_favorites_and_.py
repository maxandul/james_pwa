"""Add household article favorites and archive state

Revision ID: eebb352b7301
Revises: e691ea9e9398
Create Date: 2026-11-01 17:28:41.872833

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'eebb352b7301'
down_revision = 'e691ea9e9398'
branch_labels = None
depends_on = None


def upgrade():
    # SQL false compiles correctly for both Postgres and SQLite, including old rows.
    op.add_column('household_item', sa.Column('is_favorite', sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column('household_item', sa.Column('archived', sa.Boolean(), server_default=sa.false(), nullable=False))


def downgrade():
    # Native DROP COLUMN avoids rebuilding a parent table referenced by activity.
    # SQLite requires 3.35+ (as provided by the supported Python 3.12 installation).
    op.drop_column('household_item', 'archived')
    op.drop_column('household_item', 'is_favorite')
