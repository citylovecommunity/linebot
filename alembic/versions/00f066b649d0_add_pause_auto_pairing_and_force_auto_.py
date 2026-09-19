"""add pause_auto_pairing to campaign and force_auto_pairing to member

Revision ID: 00f066b649d0
Revises: e18ab3154221
Create Date: 2026-09-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '00f066b649d0'
down_revision: Union[str, Sequence[str], None] = 'e18ab3154221'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('campaign', sa.Column(
        'pause_auto_pairing', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('member', sa.Column(
        'force_auto_pairing', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('member', 'force_auto_pairing')
    op.drop_column('campaign', 'pause_auto_pairing')
