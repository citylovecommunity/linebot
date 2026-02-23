"""change selected_time to selected_date

Revision ID: 4e9e45735ba7
Revises: 4e2bf3be7878
Create Date: 2025-10-06 20:49:20.215563

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4e9e45735ba7'
down_revision: Union[str, Sequence[str], None] = '4e2bf3be7878'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        """
        alter table matching
        alter selected_time type date;
        
        alter table matching
        rename selected_time to  selected_date;
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(
        """
        alter table matching
        alter selected_date to  selected_time;
        
        alter table matching
        alter selected_time type timestamptz;
        """
    )
