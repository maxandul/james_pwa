"""Add shared recipes and stock integration

Revision ID: 7a4224e5e7e4
Revises: 61d8f0ac39b2
Create Date: 2026-11-03 14:32:59.258275

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7a4224e5e7e4'
down_revision = '61d8f0ac39b2'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('cooking_action',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('household_id', sa.Integer(), nullable=False),
    sa.Column('request_id', sa.String(length=36), nullable=False),
    sa.Column('fingerprint', sa.String(length=64), nullable=False),
    sa.ForeignKeyConstraint(['household_id'], ['household.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('household_id', 'request_id', name='cooking_action_request')
    )
    with op.batch_alter_table('cooking_action', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_cooking_action_household_id'), ['household_id'], unique=False)

    op.create_table('recipe_category',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('household_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=60), nullable=False),
    sa.Column('name_key', sa.String(length=240), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['household_id'], ['household.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('household_id', 'name_key', name='recipe_category_household_name')
    )
    with op.batch_alter_table('recipe_category', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_recipe_category_household_id'), ['household_id'], unique=False)

    op.create_table('recipe',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('household_id', sa.Integer(), nullable=False),
    sa.Column('category_id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=160), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('servings', sa.Numeric(precision=10, scale=3), nullable=False),
    sa.Column('yield_unit', sa.String(length=30), nullable=False),
    sa.Column('prep_minutes', sa.Integer(), nullable=False),
    sa.Column('cook_minutes', sa.Integer(), nullable=False),
    sa.Column('rest_minutes', sa.Integer(), nullable=False),
    sa.Column('steps', sa.JSON(), nullable=False),
    sa.Column('tags', sa.JSON(), nullable=False),
    sa.Column('source', sa.String(length=1000), nullable=False),
    sa.Column('is_favorite', sa.Boolean(), nullable=False),
    sa.Column('image', sa.LargeBinary(), nullable=True),
    sa.Column('created_by', sa.Integer(), nullable=False),
    sa.Column('updated_by', sa.Integer(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.CheckConstraint('servings > 0', name='recipe_servings'),
    sa.ForeignKeyConstraint(['category_id'], ['recipe_category.id'], ),
    sa.ForeignKeyConstraint(['created_by'], ['user.id'], ),
    sa.ForeignKeyConstraint(['household_id'], ['household.id'], ),
    sa.ForeignKeyConstraint(['updated_by'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('recipe', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_recipe_household_id'), ['household_id'], unique=False)

    op.create_table('recipe_ingredient',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('recipe_id', sa.Integer(), nullable=False),
    sa.Column('item_id', sa.Integer(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('amount', sa.Numeric(precision=12, scale=3), nullable=True),
    sa.Column('unit', sa.String(length=30), nullable=False),
    sa.Column('group', sa.String(length=60), nullable=False),
    sa.Column('detail', sa.String(length=160), nullable=False),
    sa.Column('is_staple', sa.Boolean(), nullable=False),
    sa.CheckConstraint('amount IS NULL OR amount > 0', name='recipe_ingredient_amount'),
    sa.ForeignKeyConstraint(['item_id'], ['household_item.id'], ),
    sa.ForeignKeyConstraint(['recipe_id'], ['recipe.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('recipe_ingredient', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_recipe_ingredient_recipe_id'), ['recipe_id'], unique=False)

    op.create_table('recipe_note',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('recipe_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['recipe_id'], ['recipe.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('recipe_note', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_recipe_note_recipe_id'), ['recipe_id'], unique=False)

    with op.batch_alter_table('shopping_need', schema=None) as batch_op:
        batch_op.add_column(sa.Column('recipe_context', sa.JSON(), server_default=sa.text("'[]'"), nullable=False))



def downgrade():
    with op.batch_alter_table('shopping_need', schema=None) as batch_op:
        batch_op.drop_column('recipe_context')

    with op.batch_alter_table('recipe_note', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_recipe_note_recipe_id'))

    op.drop_table('recipe_note')
    with op.batch_alter_table('recipe_ingredient', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_recipe_ingredient_recipe_id'))

    op.drop_table('recipe_ingredient')
    with op.batch_alter_table('recipe', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_recipe_household_id'))

    op.drop_table('recipe')
    with op.batch_alter_table('recipe_category', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_recipe_category_household_id'))

    op.drop_table('recipe_category')
    with op.batch_alter_table('cooking_action', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_cooking_action_household_id'))

    op.drop_table('cooking_action')
