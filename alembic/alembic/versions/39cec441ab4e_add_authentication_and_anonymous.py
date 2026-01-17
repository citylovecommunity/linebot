"""add authentication and anonymous

Revision ID: 39cec441ab4e
Revises: e3c2c53f7d56
Create Date: 2026-01-17 23:17:01.079531

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '39cec441ab4e'
down_revision: Union[str, Sequence[str], None] = 'e3c2c53f7d56'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("member", sa.Column("is_authenticated", sa.Boolean))
    op.add_column("member", sa.Column("is_anonymous", sa.Boolean))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("member", "is_authenticated")
    op.drop_column("member", "is_anonymous")
