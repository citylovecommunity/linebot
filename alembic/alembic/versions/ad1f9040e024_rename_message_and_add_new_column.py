"""rename message and add new column

Revision ID: ad1f9040e024
Revises: b4937a33bd5c
Create Date: 2026-01-13 00:29:43.501163

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ad1f9040e024'
down_revision: Union[str, Sequence[str], None] = 'b4937a33bd5c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Rename match_id to matching_id in message table
    op.alter_column('message', 'match_id', new_column_name='matching_id')
    # Add is_system_notification to message table
    op.add_column('message', sa.Column('is_system_notification',
                  sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    # Revert column name change in message table
    op.alter_column('message', 'matching_id', new_column_name='match_id')
    # Remove is_system_notification from message table
    op.drop_column('message', 'is_system_notification')
