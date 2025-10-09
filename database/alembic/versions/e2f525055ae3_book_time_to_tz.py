"""book_time_to tz

Revision ID: e2f525055ae3
Revises: 7614fdaab3a6
Create Date: 2025-10-08 22:30:58.346121

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e2f525055ae3'
down_revision: Union[str, Sequence[str], None] = '7614fdaab3a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        """
        alter table matching
        drop book_time;
        
        alter table matching
        add book_time timestamp with time zone;
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(
        """
        alter table matching
        drop book_time;
        
        alter table matching
        add book_time time;
        """
    )
