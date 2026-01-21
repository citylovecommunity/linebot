"""add: birthday

Revision ID: 25d76c1f9cd5
Revises: 00acaec8f80b
Create Date: 2026-01-18 20:23:57.854923

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '25d76c1f9cd5'
down_revision: Union[str, Sequence[str], None] = '00acaec8f80b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("member", sa.Column("birthday", sa.Date))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("member", "birthday")
