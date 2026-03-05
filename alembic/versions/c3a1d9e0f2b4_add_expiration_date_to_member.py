"""add expiration_date to member

Revision ID: c3a1d9e0f2b4
Revises: ba5cfbfdc962
Create Date: 2026-03-05

"""
from alembic import op
import sqlalchemy as sa

revision = 'c3a1d9e0f2b4'
down_revision = 'ba5cfbfdc962'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('member', sa.Column('expiration_date', sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column('member', 'expiration_date')
