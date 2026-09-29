"""add is_broadcast to group_message for pinned admin announcements

Revision ID: 9d3f6b1c2a4e
Revises: ff9082ce5cd7
Create Date: 2026-09-29 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9d3f6b1c2a4e'
down_revision: Union[str, Sequence[str], None] = 'ff9082ce5cd7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('group_message', sa.Column(
        'is_broadcast', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('group_message', 'is_broadcast')
