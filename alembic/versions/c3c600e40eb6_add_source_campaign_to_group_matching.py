"""add source_campaign to group_matching

Revision ID: c3c600e40eb6
Revises: 9e4f7c2a1b3d
Create Date: 2026-07-08 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3c600e40eb6'
down_revision: Union[str, Sequence[str], None] = '9e4f7c2a1b3d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('group_matching', sa.Column('source_campaign', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('group_matching', 'source_campaign')
