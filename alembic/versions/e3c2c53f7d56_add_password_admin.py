"""add password, admin


Revision ID: e3c2c53f7d56
Revises: ad1f9040e024
Create Date: 2026-01-17 21:57:08.525538

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e3c2c53f7d56'
down_revision: Union[str, Sequence[str], None] = 'ad1f9040e024'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("member", sa.Column("password_hash", sa.String(255)))
    op.add_column("member", sa.Column("is_admin", sa.Boolean))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("member", "password_hash")
    op.drop_column("member", "is_admin")
