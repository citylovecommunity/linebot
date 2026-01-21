"""add updated_at

Revision ID: 00acaec8f80b
Revises: 8be2df913c9d
Create Date: 2026-01-18 16:26:28.278180

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '00acaec8f80b'
down_revision: Union[str, Sequence[str], None] = '8be2df913c9d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("member", sa.Column(
        'updated_at', sa.DateTime(), server_default=sa.func.now()))
    op.add_column("date_proposal",  sa.Column(
        'updated_at', sa.DateTime(), server_default=sa.func.now()))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("member", 'updated_at')
    op.drop_column("date_proposal", 'updated_at')
