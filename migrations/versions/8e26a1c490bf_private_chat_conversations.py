"""Private chat conversations; retain and group the existing history."""
from uuid import NAMESPACE_URL, uuid5
from alembic import op
import sqlalchemy as sa

revision = '8e26a1c490bf'
down_revision = '9c6ef1a87b20'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('chat_conversation',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('household_id', sa.Integer(), sa.ForeignKey('household.id'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('title', sa.String(100), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False))
    op.create_index('ix_chat_conversation_household_id', 'chat_conversation', ['household_id'])
    op.create_index('ix_chat_conversation_user_id', 'chat_conversation', ['user_id'])
    with op.batch_alter_table('chat_turn') as batch:
        batch.add_column(sa.Column('conversation_id', sa.String(36), nullable=True))
        batch.create_foreign_key('fk_chat_turn_conversation_id', 'chat_conversation', ['conversation_id'], ['id'])
        batch.create_index('ix_chat_turn_conversation_id', ['conversation_id'])
    connection = op.get_bind()
    groups = connection.execute(sa.text('SELECT user_id, household_id, MAX(created_at) AS updated_at FROM chat_turn GROUP BY user_id, household_id')).mappings().all()
    conversations = sa.table('chat_conversation', sa.column('id'), sa.column('user_id'), sa.column('household_id'), sa.column('title'), sa.column('updated_at'))
    for group in groups:
        identifier = str(uuid5(NAMESPACE_URL, f"james:legacy-chat:{group['user_id']}:{group['household_id']}"))
        connection.execute(conversations.insert().values(id=identifier, user_id=group['user_id'], household_id=group['household_id'], title='Bisheriger Verlauf', updated_at=group['updated_at']))
        connection.execute(sa.text('UPDATE chat_turn SET conversation_id=:conversation WHERE user_id=:user AND household_id=:household'), dict(conversation=identifier, user=group['user_id'], household=group['household_id']))


def downgrade():
    with op.batch_alter_table('chat_turn') as batch:
        batch.drop_index('ix_chat_turn_conversation_id')
        batch.drop_constraint('fk_chat_turn_conversation_id', type_='foreignkey')
        batch.drop_column('conversation_id')
    op.drop_table('chat_conversation')
