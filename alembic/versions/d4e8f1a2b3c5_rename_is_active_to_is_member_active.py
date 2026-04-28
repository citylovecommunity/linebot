"""rename is_active to is_member_active on member

Revision ID: d4e8f1a2b3c5
Revises: c9f1a3e5b2d7
Create Date: 2026-04-28 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'd4e8f1a2b3c5'
down_revision: Union[str, Sequence[str], None] = 'c9f1a3e5b2d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('member', 'is_active', new_column_name='is_member_active')


def downgrade() -> None:
    op.alter_column('member', 'is_member_active', new_column_name='is_active')
