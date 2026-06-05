"""add group session system (Phase A)

Revision ID: a1b2c3d4e5f6
Revises: f3e1a2b0c9d8
Create Date: 2026-06-03

Adds:
  - group_membership table (replaces group_members M2M, adds avatar/ghost/referral columns)
  - group_badge table (Phase-4 anonymous feedback)
  - new columns on group_matching (expires_at, region, opener, meet details, reminder tracking)
  - new columns on member (activity_label, companion_score, observer_since, observer_offense_count)
"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = '996f6289572c'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Member: activity label & companion score ──────────────────────────────
    op.execute("""
        ALTER TABLE member
        ADD COLUMN IF NOT EXISTS activity_label VARCHAR NOT NULL DEFAULT 'TRAVELER',
        ADD COLUMN IF NOT EXISTS companion_score INTEGER NOT NULL DEFAULT 0,
        ADD COLUMN IF NOT EXISTS observer_since TIMESTAMPTZ,
        ADD COLUMN IF NOT EXISTS observer_offense_count INTEGER NOT NULL DEFAULT 0
    """)

    # ── GroupMatching: lifecycle & meetup columns ─────────────────────────────
    op.execute("""
        ALTER TABLE group_matching
        ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP,
        ADD COLUMN IF NOT EXISTS region VARCHAR,
        ADD COLUMN IF NOT EXISTS opener_member_id INTEGER REFERENCES member(id),
        ADD COLUMN IF NOT EXISTS meet_location VARCHAR,
        ADD COLUMN IF NOT EXISTS meet_time TIMESTAMP,
        ADD COLUMN IF NOT EXISTS meet_notes VARCHAR,
        ADD COLUMN IF NOT EXISTS summary_submitted_by_id INTEGER REFERENCES member(id),
        ADD COLUMN IF NOT EXISTS meetup_reminder_sent_at TIMESTAMPTZ
    """)

    # Backfill expires_at for any existing active groups (15 days from creation)
    op.execute("""
        UPDATE group_matching
        SET expires_at = created_at + INTERVAL '15 days'
        WHERE expires_at IS NULL
    """)

    # ── group_membership: replaces group_members ──────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS group_membership (
            id          SERIAL PRIMARY KEY,
            group_id    INTEGER NOT NULL REFERENCES group_matching(id),
            member_id   INTEGER NOT NULL REFERENCES member(id),
            joined_at   TIMESTAMP NOT NULL DEFAULT NOW(),
            session_avatar VARCHAR,
            message_count  INTEGER NOT NULL DEFAULT 0,
            clicked_wish_button BOOLEAN NOT NULL DEFAULT FALSE,
            final_label VARCHAR,
            is_referral BOOLEAN NOT NULL DEFAULT FALSE,
            referred_by_id INTEGER REFERENCES member(id),
            UNIQUE (group_id, member_id)
        )
    """)

    # Migrate existing rows from the old M2M table only if it exists
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'group_members'
            ) THEN
                INSERT INTO group_membership (group_id, member_id, joined_at)
                SELECT group_id, member_id, NOW()
                FROM group_members
                ON CONFLICT (group_id, member_id) DO NOTHING;

                DROP TABLE group_members;
            END IF;
        END $$;
    """)

    # ── group_badge: Phase-4 anonymous feedback ───────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS group_badge (
            id             SERIAL PRIMARY KEY,
            group_id       INTEGER NOT NULL REFERENCES group_matching(id),
            from_member_id INTEGER NOT NULL REFERENCES member(id),
            to_member_id   INTEGER NOT NULL REFERENCES member(id),
            badge_type     VARCHAR NOT NULL,
            created_at     TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_group_membership_group_id
            ON group_membership (group_id)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_group_membership_member_id
            ON group_membership (member_id)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_group_badge_group_id
            ON group_badge (group_id)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS group_badge")

    # Recreate the old M2M table and repopulate from group_membership (if it exists)
    op.execute("""
        CREATE TABLE IF NOT EXISTS group_members (
            group_id  INTEGER NOT NULL REFERENCES group_matching(id),
            member_id INTEGER NOT NULL REFERENCES member(id),
            PRIMARY KEY (group_id, member_id)
        )
    """)
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'group_membership'
            ) THEN
                INSERT INTO group_members (group_id, member_id)
                SELECT group_id, member_id FROM group_membership
                ON CONFLICT DO NOTHING;
            END IF;
        END $$;
    """)
    op.execute("DROP TABLE IF EXISTS group_membership")

    op.execute("""
        ALTER TABLE group_matching
        DROP COLUMN IF EXISTS expires_at,
        DROP COLUMN IF EXISTS region,
        DROP COLUMN IF EXISTS opener_member_id,
        DROP COLUMN IF EXISTS meet_location,
        DROP COLUMN IF EXISTS meet_time,
        DROP COLUMN IF EXISTS meet_notes,
        DROP COLUMN IF EXISTS summary_submitted_by_id,
        DROP COLUMN IF EXISTS meetup_reminder_sent_at
    """)

    op.execute("""
        ALTER TABLE member
        DROP COLUMN IF EXISTS activity_label,
        DROP COLUMN IF EXISTS companion_score,
        DROP COLUMN IF EXISTS observer_since,
        DROP COLUMN IF EXISTS observer_offense_count
    """)
