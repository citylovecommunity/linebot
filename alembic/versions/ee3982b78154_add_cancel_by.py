"""add cancel by

Revision ID: ee3982b78154
Revises: 25d76c1f9cd5
Create Date: 2026-01-19 00:01:24.111124

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ee3982b78154'
down_revision: Union[str, Sequence[str], None] = '25d76c1f9cd5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("matching", sa.Column("cancel_by_id", sa.Integer))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("matching", "cancel_by_id")
