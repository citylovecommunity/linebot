"""drop all uness constraints

Revision ID: d807004aac7f
Revises: 05b2d802e527
Create Date: 2025-10-16 14:50:53.524416

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd807004aac7f'
down_revision: Union[str, Sequence[str], None] = '05b2d802e527'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        """
        ALTER TABLE matching_state_history
        DROP CONSTRAINT IF EXISTS matching_fk;
        
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    pass
