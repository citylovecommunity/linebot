"""add test member

Revision ID: 61fb28e95f76
Revises: e2f525055ae3
Create Date: 2025-10-14 14:52:02.535648

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '61fb28e95f76'
down_revision: Union[str, Sequence[str], None] = '7614fdaab3a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        """
        alter table member
        add column is_test boolean;
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    """
    alter table member
    drop column is_test;
    """
