"""add campaign photo urls

Revision ID: 5fbca5080ced
Revises: 36460a84026c
Create Date: 2026-08-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '5fbca5080ced'
down_revision: Union[str, Sequence[str], None] = '36460a84026c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('campaign', sa.Column('photo1_url', sa.String(), nullable=True))
    op.add_column('campaign', sa.Column('photo2_url', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('campaign', 'photo2_url')
    op.drop_column('campaign', 'photo1_url')
