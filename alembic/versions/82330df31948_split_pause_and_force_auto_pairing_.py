"""split pause/force auto pairing into 1:1 and group variants

Revision ID: 82330df31948
Revises: 00f066b649d0
Create Date: 2026-09-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '82330df31948'
down_revision: Union[str, Sequence[str], None] = '00f066b649d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column('campaign', 'pause_auto_pairing', new_column_name='pause_one_on_one_pairing')
    op.add_column('campaign', sa.Column(
        'pause_group_pairing', sa.Boolean(), nullable=False, server_default=sa.false()))

    op.alter_column('member', 'force_auto_pairing', new_column_name='force_one_on_one_pairing')
    op.add_column('member', sa.Column(
        'force_group_pairing', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('member', 'force_group_pairing')
    op.alter_column('member', 'force_one_on_one_pairing', new_column_name='force_auto_pairing')

    op.drop_column('campaign', 'pause_group_pairing')
    op.alter_column('campaign', 'pause_one_on_one_pairing', new_column_name='pause_auto_pairing')
