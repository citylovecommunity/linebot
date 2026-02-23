"""add accepted

Revision ID: 8be2df913c9d
Revises: 3731c0764c8e
Create Date: 2026-01-18 16:15:38.324728

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8be2df913c9d'
down_revision: Union[str, Sequence[str], None] = '3731c0764c8e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("matching", sa.Column("object_accepted", sa.Boolean))
    op.add_column("matching", sa.Column("subject_accepted", sa.Boolean))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("matching", "subject_accepted")
    op.drop_column("matching", "object_accepted")
