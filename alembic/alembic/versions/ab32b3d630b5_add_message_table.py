"""add Message table

Revision ID: ab32b3d630b5
Revises: e63c9c0561c7
Create Date: 2026-01-11 19:29:53.736417

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ab32b3d630b5'
down_revision: Union[str, Sequence[str], None] = 'e63c9c0561c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'message',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('timestamp', sa.DateTime, nullable=False,
                  server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('user_id', sa.Integer, sa.ForeignKey(
            'member.id'), nullable=False),
        sa.Column('match_id', sa.Integer, sa.ForeignKey(
            'matching.id'), nullable=False)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('message')
