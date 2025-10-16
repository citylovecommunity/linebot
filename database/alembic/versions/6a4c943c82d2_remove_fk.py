"""remove fk

Revision ID: 6a4c943c82d2
Revises: 61fb28e95f76
Create Date: 2025-10-15 18:25:22.760498

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6a4c943c82d2'
down_revision: Union[str, Sequence[str], None] = '61fb28e95f76'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        """
        ALTER TABLE matching
        DROP CONSTRAINT IF EXISTS object_fk_member;
        
        ALTER TABLE matching
        DROP CONSTRAINT IF EXISTS subject_fk_member;
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    pass
