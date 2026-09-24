"""add message_template table

Revision ID: b1c2d3e4f5a6
Revises: 03369213374e
Create Date: 2026-09-24 00:00:00.000000

"""
from datetime import datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ff9082ce5cd7'
down_revision: Union[str, Sequence[str], None] = '03369213374e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


message_template = sa.table(
    'message_template',
    sa.column('key', sa.String),
    sa.column('content', sa.String),
    sa.column('updated_at', sa.DateTime),
)

# Seeded with the wording that was previously hardcoded in
# services/messaging.py:collect_new_match_texts, so behavior is unchanged
# until an admin edits these via the admin panel.
_DEFAULTS = {
    'new_match_default': (
        "推薦你認識新朋友的時間來囉！\n\n"
        "您們可以一起相約喝個咖啡，\n"
        "或是本季我們主打大家一起認識現火熱的匹克球運動，\n"
        "歡迎你們一起相約共襄盛舉！\n"
        "詳見對話框的任務牆～\n\n"
        "{url}"
    ),
    'new_match_pickleball': (
        "Hi 本週你的新球友來了！\n"
        "→ 點此查看 {url}\n"
        "提醒：打球時間地點由大家自行約定，不限任何特定時間和地點"
    ),
}


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'message_template',
        sa.Column('key', sa.String(), primary_key=True),
        sa.Column('content', sa.String(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )

    now = datetime.now()
    op.bulk_insert(message_template, [
        {'key': key, 'content': content, 'updated_at': now}
        for key, content in _DEFAULTS.items()
    ])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('message_template')
