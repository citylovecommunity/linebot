"""matching add metric

Revision ID: 0759baaded51
Revises: d807004aac7f
Create Date: 2025-11-14 18:11:53.782180

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0759baaded51'
down_revision: Union[str, Sequence[str], None] = 'd807004aac7f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        """
        alter table matching
        add column grading_metric int;
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(
        """
        alter table matching
        drop column grading_metric;
        """
    )
