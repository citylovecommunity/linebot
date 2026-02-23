"""add cool_name

Revision ID: 9c78f2720e27
Revises: ee3982b78154
Create Date: 2026-01-19 00:20:05.916902

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9c78f2720e27'
down_revision: Union[str, Sequence[str], None] = 'ee3982b78154'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("matching", sa.Column("cool_name", sa.String))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("matching", "cool_name")
