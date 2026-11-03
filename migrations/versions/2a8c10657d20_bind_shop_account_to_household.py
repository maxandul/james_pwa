"""Serialize the shared shop account per household.

Revision ID: 2a8c10657d20
Revises: 11d03bec0cc7
"""
from alembic import op
import sqlalchemy as sa

revision = '2a8c10657d20'
down_revision = '11d03bec0cc7'
branch_labels = None
depends_on = None


def upgrade():
    # Refuse ambiguous old parallel sessions rather than silently dropping one.
    connection = op.get_bind()
    duplicates = connection.execute(sa.text("SELECT household_id FROM shop_login WHERE state != 'closed' GROUP BY household_id HAVING COUNT(*) > 1")).first()
    if duplicates:
        raise RuntimeError('Offene parallele Shop-Anmeldungen zuerst bereinigen.')
    with op.batch_alter_table('shop_login') as batch:
        batch.add_column(sa.Column('active_household_id', sa.Integer(), nullable=True))
        batch.create_unique_constraint('uq_shop_login_active_household_id', ['active_household_id'])
    connection.execute(sa.text("UPDATE shop_login SET active_household_id = household_id WHERE state != 'closed'"))


def downgrade():
    with op.batch_alter_table('shop_login') as batch:
        batch.drop_constraint('uq_shop_login_active_household_id', type_='unique')
        batch.drop_column('active_household_id')
