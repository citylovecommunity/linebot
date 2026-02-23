"""add sudden_change_time_history table

Revision ID: 4e2bf3be7878
Revises: 30705acd58bd
Create Date: 2025-10-01 23:54:15.752066

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4e2bf3be7878'
down_revision: Union[str, Sequence[str], None] = '30705acd58bd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("""
               CREATE TABLE sudden_change_time_history (
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
               drop table sudden_change_time_history;
               """)
