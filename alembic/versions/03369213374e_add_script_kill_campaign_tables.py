"""add script-kill campaign tables

Revision ID: 03369213374e
Revises: 82330df31948
Create Date: 2026-09-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '03369213374e'
down_revision: Union[str, Sequence[str], None] = '82330df31948'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'script_kill_campaign',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('roles', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('member.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )

    op.create_table(
        'script_kill_campaign_group',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('campaign_id', sa.Integer(),
                  sa.ForeignKey('script_kill_campaign.id', ondelete='CASCADE'), nullable=False),
        sa.Column('group_id', sa.Integer(),
                  sa.ForeignKey('group_matching.id', ondelete='CASCADE'), nullable=False),
        sa.Column('added_at', sa.DateTime(), nullable=False),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('campaign_id', 'group_id', name='uq_script_kill_campaign_group'),
    )
    op.create_index('ix_script_kill_campaign_group_campaign_id', 'script_kill_campaign_group', ['campaign_id'])
    op.create_index('ix_script_kill_campaign_group_group_id', 'script_kill_campaign_group', ['group_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_script_kill_campaign_group_group_id', table_name='script_kill_campaign_group')
    op.drop_index('ix_script_kill_campaign_group_campaign_id', table_name='script_kill_campaign_group')
    op.drop_table('script_kill_campaign_group')
    op.drop_table('script_kill_campaign')
