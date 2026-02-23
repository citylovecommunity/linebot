"""create change_time_history

Revision ID: e5ec16e6f0fe
Revises: d6ff9b3acc76
Create Date: 2025-09-29 14:55:41.763917

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5ec16e6f0fe'
down_revision: Union[str, Sequence[str], None] = 'd6ff9b3acc76'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("""
               CREATE TABLE change_time_history (
        id integer PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
        member_id integer,
        matching_id integer,
        change_time_message text,
        created_at timestamp with time zone
        );
               """)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("""
               drop table change_time_history;
               """)
