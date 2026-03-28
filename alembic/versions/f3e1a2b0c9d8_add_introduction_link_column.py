"""add introduction_link column to member

Revision ID: f3e1a2b0c9d8
Revises: d9a086aab71d
Create Date: 2026-03-28

"""
from alembic import op
import sqlalchemy as sa

revision = 'f3e1a2b0c9d8'
down_revision = 'd9a086aab71d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE member
        ADD COLUMN IF NOT EXISTS introduction_link TEXT
    """)
    # Backfill from user_info JSONB for existing members
    op.execute("""
        UPDATE member
        SET introduction_link = user_info->>'會員介紹頁網址'
        WHERE introduction_link IS NULL
          AND user_info->>'會員介紹頁網址' IS NOT NULL
          AND user_info->>'會員介紹頁網址' != ''
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE member DROP COLUMN IF EXISTS introduction_link")
