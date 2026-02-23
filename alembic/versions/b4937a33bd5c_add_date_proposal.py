"""add date proposal

Revision ID: b4937a33bd5c
Revises: 4f8a8c25c18d
Create Date: 2026-01-12 23:38:54.433922

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b4937a33bd5c'
down_revision: Union[str, Sequence[str], None] = '4f8a8c25c18d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "date_proposal",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("matching_id", sa.Integer, sa.ForeignKey(
            "matching.id"), nullable=False),
        sa.Column("proposer_id", sa.Integer, sa.ForeignKey(
            "member.id"), nullable=False),
        sa.Column("restaurant_name", sa.String, nullable=False),
        sa.Column("proposed_datetime", sa.DateTime, nullable=False),
        sa.Column("booker_role", sa.String,
                  nullable=False, server_default="none"),
        sa.Column("status", sa.String, nullable=False,
                  server_default="pending"),
        sa.Column("created_at", sa.DateTime, nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("date_proposal")
