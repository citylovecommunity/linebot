"""change to usable

Revision ID: 0ea55f2c2b99
Revises: 
Create Date: 2025-09-28 14:15:53.270127

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0ea55f2c2b99'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("""
               alter table matching 
               add column last_change_state_at timestamptz;
               """)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("""
               alter table matching 
               drop column last_change_state_at;
               """)
