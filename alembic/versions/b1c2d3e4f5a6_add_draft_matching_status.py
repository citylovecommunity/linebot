"""add DRAFT to matching status enum

Revision ID: b1c2d3e4f5a6
Revises: aee305de5c68
Create Date: 2026-04-01 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, Sequence[str], None] = 'aee305de5c68'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add DRAFT to matching status CHECK constraint."""
    # Drop the old CHECK constraint and recreate with DRAFT included.
    # The constraint name follows SQLAlchemy's naming convention for non-native enums.
    op.execute("ALTER TABLE matching DROP CONSTRAINT IF EXISTS matching_status_check")
    op.execute(
        "ALTER TABLE matching ADD CONSTRAINT matching_status_check "
        "CHECK (status IN ('ACTIVE', 'COMPLETED', 'CANCELLED', 'DRAFT'))"
    )


def downgrade() -> None:
    """Remove DRAFT from matching status CHECK constraint."""
    # First set any DRAFT rows back to CANCELLED before dropping the constraint
    op.execute("UPDATE matching SET status = 'CANCELLED' WHERE status = 'DRAFT'")
    op.execute("ALTER TABLE matching DROP CONSTRAINT IF EXISTS matching_status_check")
    op.execute(
        "ALTER TABLE matching ADD CONSTRAINT matching_status_check "
        "CHECK (status IN ('ACTIVE', 'COMPLETED', 'CANCELLED'))"
    )
