"""add matching status

Revision ID: 3731c0764c8e
Revises: 39cec441ab4e
Create Date: 2026-01-18 13:04:42.244566

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3731c0764c8e'
down_revision: Union[str, Sequence[str], None] = 'e3c2c53f7d56'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("matching", sa.Column("status", sa.String))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("matching", "status")
