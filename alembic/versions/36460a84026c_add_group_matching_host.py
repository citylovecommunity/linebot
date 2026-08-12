"""add group_matching host_member_id (主揪)

Revision ID: 36460a84026c
Revises: 64ab7dddbf27
Create Date: 2026-08-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '36460a84026c'
down_revision: Union[str, Sequence[str], None] = '64ab7dddbf27'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('group_matching', sa.Column('host_member_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'group_matching_host_member_id_fkey',
        'group_matching', 'member',
        ['host_member_id'], ['id'],
    )


def downgrade() -> None:
    op.drop_constraint('group_matching_host_member_id_fkey', 'group_matching', type_='foreignkey')
    op.drop_column('group_matching', 'host_member_id')
