"""create sending_history

Revision ID: d6ff9b3acc76
Revises: 0ea55f2c2b99
Create Date: 2025-09-29 14:44:33.080796

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd6ff9b3acc76'
down_revision: Union[str, Sequence[str], None] = '0ea55f2c2b99'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        """
        CREATE TABLE sending_history (
        id integer PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
        matching_id integer,
        body text,
        send_at timestamp with time zone,
        send_to text
        );
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(
        """
        drop table sending_history;
        """
    )
