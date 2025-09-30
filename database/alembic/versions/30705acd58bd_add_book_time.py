"""add book time

Revision ID: 30705acd58bd
Revises: e5ec16e6f0fe
Create Date: 2025-09-29 20:38:40.979767

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '30705acd58bd'
down_revision: Union[str, Sequence[str], None] = 'e5ec16e6f0fe'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("""
               alter table matching 
               add column book_time time;
               """)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("""
               alter table matching
               drop column book_time;
               """)
