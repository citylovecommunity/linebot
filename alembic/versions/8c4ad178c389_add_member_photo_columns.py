"""add member photo columns

Revision ID: 8c4ad178c389
Revises: 5fbca5080ced
Create Date: 2026-09-16 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '8c4ad178c389'
down_revision: Union[str, Sequence[str], None] = '5fbca5080ced'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('member', sa.Column('photo_url', sa.String(), nullable=True))
    op.add_column('member', sa.Column('photo_public_id', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('member', 'photo_public_id')
    op.drop_column('member', 'photo_url')
