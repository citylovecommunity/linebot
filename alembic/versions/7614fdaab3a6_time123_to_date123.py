"""time123 to date123

Revision ID: 7614fdaab3a6
Revises: 4e9e45735ba7
Create Date: 2025-10-06 20:56:59.110907

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7614fdaab3a6'
down_revision: Union[str, Sequence[str], None] = '4e9e45735ba7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        """
        alter table matching
        alter time1 type date,
        alter time2 type date,
        alter time3 type date;
        
    
        alter table matching
        rename time1 to  date1;
        
        alter table matching
        rename time2 to  date2;
        
        alter table matching
        rename time3 to  date3;
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(
        """
        alter table matching
        rename date1 to  time1;
        
        alter table matching
        rename date2 to  time2;
        
        alter table matching
        rename date3 to  time3;s
        
        
        alter table matching
        alter time1 type timestamptz,
        alter time2 type timestamptz,
        alter time3 type timestamptz;
        """
    )
