"""add group_message recipient for private coach notes

Revision ID: e18ab3154221
Revises: 8c4ad178c389
Create Date: 2026-09-16 10:13:03.043621

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e18ab3154221'
down_revision: Union[str, Sequence[str], None] = '8c4ad178c389'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('group_message', sa.Column('recipient_id', sa.Integer(), nullable=True))
    op.add_column('group_message', sa.Column(
        'is_coach_note', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_foreign_key(None, 'group_message', 'member', ['recipient_id'], ['id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(None, 'group_message', type_='foreignkey')
    op.drop_column('group_message', 'is_coach_note')
    op.drop_column('group_message', 'recipient_id')
