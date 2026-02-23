"""add obj metric

Revision ID: 755bd26686c2
Revises: 0759baaded51
Create Date: 2025-12-16 00:11:03.257976

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '755bd26686c2'
down_revision: Union[str, Sequence[str], None] = '0759baaded51'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        """
        alter table matching
        add column obj_grading_metric int;
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(
        """
        alter table matching
        drop column obj_grading_metric;
        """
    )
