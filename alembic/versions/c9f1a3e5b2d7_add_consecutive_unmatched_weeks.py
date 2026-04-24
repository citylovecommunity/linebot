"""add consecutive_unmatched_weeks to member

Revision ID: c9f1a3e5b2d7
Revises: 6df0dce0882d
Create Date: 2026-04-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'c9f1a3e5b2d7'
down_revision: Union[str, Sequence[str], None] = '6df0dce0882d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('member', sa.Column(
        'consecutive_unmatched_weeks', sa.Integer(), nullable=False, server_default='0'
    ))


def downgrade() -> None:
    op.drop_column('member', 'consecutive_unmatched_weeks')
