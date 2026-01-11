"""member table recreate

Revision ID: 05b2d802e527
Revises: 6a4c943c82d2
Create Date: 2025-10-15 22:31:04.544395

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '05b2d802e527'
down_revision: Union[str, Sequence[str], None] = '6a4c943c82d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        """
        drop table member;
        
        CREATE TABLE member (
            id SERIAL PRIMARY KEY,                        -- auto-increment ID
            name TEXT NOT NULL,                           -- member name
            gender TEXT,                                  -- e.g., 'M', 'F', 'Other'
            phone_number TEXT UNIQUE NOT NULL,            -- unique phone number
            is_active BOOLEAN DEFAULT TRUE,               -- active flag
            email TEXT,                                   -- email address
            id_card_no TEXT,                              -- national ID or passport number
            fill_form_at TIMESTAMP,                        -- form submission time
            user_info JSONB,                              -- extra user info stored as JSON
            is_test BOOLEAN DEFAULT FALSE                 -- flag to mark test records
        );
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    pass
