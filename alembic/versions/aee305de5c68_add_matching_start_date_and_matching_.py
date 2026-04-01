"""add matching_start_date and matching_end_date to member

Revision ID: aee305de5c68
Revises: f3e1a2b0c9d8
Create Date: 2026-04-01 10:39:44.886285

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'aee305de5c68'
down_revision: Union[str, Sequence[str], None] = 'f3e1a2b0c9d8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('member', sa.Column('matching_start_date', sa.Date(), nullable=True))
    op.add_column('member', sa.Column('matching_end_date', sa.Date(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('member', 'matching_end_date')
    op.drop_column('member', 'matching_start_date')
