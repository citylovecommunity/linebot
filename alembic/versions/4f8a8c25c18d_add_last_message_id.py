"""add last message id

Revision ID: 4f8a8c25c18d
Revises: ab32b3d630b5
Create Date: 2026-01-12 22:50:14.173074

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4f8a8c25c18d'
down_revision: Union[str, Sequence[str], None] = 'ab32b3d630b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("matching", sa.Column("last_message_id", sa.Integer()))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("matching", "last_message_id")
