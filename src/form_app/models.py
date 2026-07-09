
import enum
import random
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import Column, DateTime, Integer, Table
from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, func
from sqlalchemy.dialects.postgresql.json import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import column_property
from sqlalchemy import select, func, and_, or_


class ProposalStatus(enum.Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    DELETED = "DELETED"


class MatchingStatus(enum.Enum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    DRAFT = "DRAFT"


class Base(DeclarativeBase):
    pass


# Association table for Member <-> Tag many-to-many
member_tag = Table(
    'member_tag',
    Base.metadata,
    Column('member_id', Integer, ForeignKey('member.id', ondelete='CASCADE'), primary_key=True),
    Column('tag_id', Integer, ForeignKey('tag.id', ondelete='CASCADE'), primary_key=True),
)


class GroupMatchingStatus(enum.Enum):
    DRAFT = "DRAFT"         # awaiting admin approval, not yet notified
    ACTIVE = "ACTIVE"
    FEEDBACK = "FEEDBACK"   # Phase 4: collecting anonymous badges
    CLOSED = "CLOSED"       # Day 15: archived
    CANCELLED = "CANCELLED"


class ActivityLabel(enum.Enum):
    TRAVELER = "TRAVELER"               # 🌱 同行者 (0–4 pts)
    ACTIVE_TRAVELER = "ACTIVE_TRAVELER" # 🌟 活躍同行者 (5–14 pts)
    SUPER_TRAVELER = "SUPER_TRAVELER"   # 🏆 超級同行者 (15+ pts)
    OBSERVER = "OBSERVER"               # 🍂 觀察者 (consecutive bad sessions)


class MemberSessionLabel(enum.Enum):
    PERFECT = "PERFECT"   # 🟢 完美同行
    GHOST = "GHOST"       # 👻 本局幽靈
    NO_SHOW = "NO_SHOW"   # 🕊️ 本局放鳥


class BadgeType(enum.Enum):
    GOOD_CHAT = "GOOD_CHAT"   # 💬 很有話聊
    PUNCTUAL = "PUNCTUAL"     # 🌟 準時好旅伴
    CARING = "CARING"         # 🍯 貼心暖洋洋
    FUNNY = "FUNNY"           # 🎭 氣氛擔當
    NO_SHOW = "NO_SHOW"       # ☕ 這次好可惜沒能見到你


# Pool of cute avatars randomly assigned per GroupMembership (no duplicates within a session).
COMPANION_AVATARS: list[str] = [
    "🐱", "🐶", "🐰", "🦊", "🐻", "🐼", "🦋", "🌸",
    "🌺", "🌻", "🍀", "🐙", "🦔", "🐿️", "🦜", "🐨",
    "🌹", "🌷", "🦩", "🐬", "🌿", "🍁", "🐧", "🦚",
    "🦌", "🐸", "🦦", "🌴", "🦁", "🐯", "🦄", "🐘",
    "🦒", "🦓", "🐊", "🦀", "🐡", "🌈", "🎋", "🌙",
]


def assign_session_avatars(count: int) -> list[str]:
    """Return `count` unique avatars sampled from the pool without replacement."""
    return random.sample(COMPANION_AVATARS, min(count, len(COMPANION_AVATARS)))


class Member(Base):
    __tablename__ = "member"
    id: Mapped[int] = mapped_column(primary_key=True)

    def get_id(self):
        # Convert the primary key to a string
        return str(self.id)

    name: Mapped[str]
    gender: Mapped[str]
    phone_number: Mapped[str] = mapped_column(
        unique=True, index=True, nullable=False)

    is_member_active: Mapped[bool] = mapped_column(default=True)

    @property
    def is_active(self) -> bool:
        return True
    updated_at: Mapped[datetime] = mapped_column(
        onupdate=datetime.now, default=datetime.now)

    birthday: Mapped[Optional[date]]

    is_test: Mapped[bool] = mapped_column(default=False)

    email: Mapped[Optional[str]]
    id_card_no: Mapped[Optional[str]]
    fill_form_at: Mapped[datetime]
    join_campaign: Mapped[Optional[str]]    # slug from campaigns.py; None = admin-created
    user_info: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=True)

    rank: Mapped[Optional[str]]
    marital_status: Mapped[Optional[str]]

    height: Mapped[Optional[int]]

    pref_min_height: Mapped[Optional[int]]
    pref_max_height: Mapped[Optional[int]]
    pref_oldest_birth_year: Mapped[Optional[int]]
    pref_youngest_birth_year: Mapped[Optional[int]]

    # Keys: 'height', 'region' — value True means hard dealbreaker, False means soft (-20 pts)
    pref_locks: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    matches_as_subject: Mapped[list["Matching"]] = relationship(
        "Matching",
        foreign_keys="Matching.subject_id",
        back_populates="subject"
    )

    matches_as_object: Mapped[list["Matching"]] = relationship(
        "Matching",
        foreign_keys="Matching.object_id",
        back_populates="object"
    )

    @property
    def all_matches(self):
        """Returns a combined list of matches where user is subject or object (excludes drafts),
        ordered by most recent message first, then by creation date."""
        matches = [
            m for m in self.matches_as_subject + self.matches_as_object
            if m.status is not MatchingStatus.DRAFT
        ]
        return sorted(matches, key=lambda m: (m.last_message_id or 0), reverse=True)

    password_hash: Mapped[Optional[str]]

    is_admin:  Mapped[Optional[bool]] = mapped_column(default=False)
    is_developer: Mapped[Optional[bool]] = mapped_column(default=False)

    line_info: Mapped[Optional["Line_Info"]] = relationship(
        back_populates="member",
        primaryjoin="Member.phone_number == Line_Info.phone_number",
        foreign_keys="Line_Info.phone_number"
    )

    last_notification_sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
    )

    last_seen_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
    )

    @property
    def is_match_ready(self):
        """Returns True if the user has all requirements for matching."""
        return bool(self.line_info and self.introduction_link)

    @property
    def missing_requirements(self):
        """Returns a list of specific missing items."""
        missing = []
        if not self.line_info:
            missing.append("line_info")
        if not self.introduction_link:
            missing.append("introduction_link")
        return missing

    @property
    def proper_name(self):
        surname = '先生' if self.gender == 'M' else '小姐'
        return self.name[0] + surname

    introduction_link: Mapped[Optional[str]]

    @property
    def blind_introduction_link(self):
        return self.user_info.get('盲約介紹卡一') if self.user_info else None

    expiration_date: Mapped[Optional[date]]

    matching_start_date: Mapped[Optional[date]]
    matching_end_date: Mapped[Optional[date]]

    # Tracks how many consecutive matching cycles this member was eligible but unmatched.
    # Reset to 0 each time they are successfully paired.
    # Used to give priority boosts and unlock re-matching with historical partners.
    consecutive_unmatched_weeks: Mapped[int] = mapped_column(default=0)

    # Group session participation (new system)
    group_memberships: Mapped[list["GroupMembership"]] = relationship(
        "GroupMembership",
        foreign_keys="GroupMembership.member_id",
        back_populates="member",
    )

    @property
    def group_matchings(self) -> list["GroupMatching"]:
        return [gm.group for gm in self.group_memberships]

    # Activity label & companion score (group feature)
    activity_label: Mapped[ActivityLabel] = mapped_column(
        SAEnum(ActivityLabel, native_enum=False, values_callable=lambda x: [e.value for e in x]),
        default=ActivityLabel.TRAVELER,
    )
    companion_score: Mapped[int] = mapped_column(default=0)
    observer_since: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    observer_offense_count: Mapped[int] = mapped_column(default=0)

    # ── Label display helpers (used by templates) ──────────────────────────
    _LABEL_META = {
        ActivityLabel.TRAVELER:       ("🌱", "同行者",     "success",   0,  5),
        ActivityLabel.ACTIVE_TRAVELER:("🌟", "活躍同行者", "primary",   5,  15),
        ActivityLabel.SUPER_TRAVELER: ("🏆", "超級同行者", "warning",   15, None),
        ActivityLabel.OBSERVER:       ("🍂", "觀察者",     "secondary", 0,  None),
    }

    @property
    def label_emoji(self) -> str:
        return self._LABEL_META.get(self.activity_label, ("🌱", "", "", 0, None))[0]

    @property
    def label_name(self) -> str:
        return self._LABEL_META.get(self.activity_label, ("", "同行者", "", 0, None))[1]

    @property
    def label_color(self) -> str:
        return self._LABEL_META.get(self.activity_label, ("", "", "success", 0, None))[2]

    @property
    def label_progress_pct(self) -> int:
        """0-100 progress bar value toward the next label tier. 100 if at max."""
        meta = self._LABEL_META.get(self.activity_label)
        if not meta:
            return 0
        _, _, _, low, high = meta
        if high is None:
            return 100
        score = self.companion_score or 0
        span = high - low
        return min(100, int((score - low) / span * 100)) if span > 0 else 0

    @property
    def label_next_at(self) -> Optional[int]:
        """Score threshold for the next label, or None if already at max / observer."""
        meta = self._LABEL_META.get(self.activity_label)
        return meta[4] if meta else None

    @property
    def observer_sleep_days(self) -> Optional[int]:
        """Remaining sleep days if OBSERVER, else None."""
        if self.activity_label != ActivityLabel.OBSERVER or not self.observer_since:
            return None
        total = 14 if (self.observer_offense_count or 0) <= 1 else 28
        from datetime import timezone as _tz
        os = self.observer_since
        if os.tzinfo is None:
            os = os.replace(tzinfo=_tz.utc)
        elapsed = (datetime.now(_tz.utc) - os).days
        return max(0, total - elapsed)

    @property
    def membership_months(self) -> Optional[int]:
        if not self.user_info:
            return None
        raw = self.user_info.get('購買的方案期數 /月（ 填寫純數字 ）', '')
        try:
            return int(str(raw).strip())
        except (ValueError, TypeError):
            return None

    @property
    def is_expiring_soon(self) -> bool:
        from datetime import date as _date
        from dateutil.relativedelta import relativedelta
        if not self.expiration_date:
            return False
        return self.expiration_date <= _date.today() + relativedelta(days=30)

    @property
    def is_expired(self) -> bool:
        from datetime import date as _date
        if not self.expiration_date:
            return False
        return self.expiration_date < _date.today()

    tags: Mapped[list['Tag']] = relationship('Tag', secondary=member_tag, back_populates='members')


class Line_Info(Base):
    __tablename__ = "line_info"

    # 1. Remove ForeignKey here.
    # This allows this column to hold values that don't exist in the 'member' table.
    phone_number: Mapped[str] = mapped_column(primary_key=True)

    user_id: Mapped[str]

    # 2. Define the relationship explicitly.
    member: Mapped[Optional["Member"]] = relationship(
        "Member",
        # Tell SQLAlchemy exactly how to join the tables
        primaryjoin="Member.phone_number == Line_Info.phone_number",
        # Explicitly label which column acts as the "foreign key" for this link
        foreign_keys=[phone_number],
        back_populates="line_info"
    )


class Matching(Base):
    __tablename__ = "matching"
    id: Mapped[int] = mapped_column(primary_key=True)
    subject_id: Mapped[int] = mapped_column(
        ForeignKey("member.id"))

    object_id: Mapped[int] = mapped_column(
        ForeignKey("member.id"))

    status: Mapped[MatchingStatus] = mapped_column(
        SAEnum(
            MatchingStatus,
            native_enum=False,
            values_callable=lambda x: [e.value for e in x]
        ),
        default=MatchingStatus.ACTIVE
    )

    cool_name: Mapped[Optional[str]]

    is_match_notified: Mapped[Optional[bool]] = mapped_column(default=False)

    cancel_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey('member.id'))

    cancel_by: Mapped["Member"] = relationship(
        foreign_keys=[cancel_by_id],
    )

    @property
    def is_active(self):
        return self.status is MatchingStatus.ACTIVE

    @property
    def is_completed(self):
        return self.status is MatchingStatus.COMPLETED

    @property
    def is_cancelled(self):
        return self.status is MatchingStatus.CANCELLED

    @property
    def is_draft(self):
        return self.status is MatchingStatus.DRAFT

    def activate(self):
        self.status = MatchingStatus.ACTIVE
        self.cancel_by_id = None

    def complete(self):
        self.status = MatchingStatus.COMPLETED

    def cancel(self, cancel_id):
        self.status = MatchingStatus.CANCELLED
        self.cancel_by_id = cancel_id

    def approve_draft(self):
        """Promote a DRAFT matching to ACTIVE and reset notification flag."""
        self.status = MatchingStatus.ACTIVE
        self.is_match_notified = False

    created_at: Mapped[datetime] = mapped_column(default=datetime.now)

    updated_at: Mapped[Optional[datetime]
                       ] = mapped_column(onupdate=datetime.now, default=datetime.now)

    grading_metric: Mapped[int]
    obj_grading_metric: Mapped[int]

    subject: Mapped["Member"] = relationship(
        "Member",
        foreign_keys=[subject_id],
        back_populates="matches_as_subject"
    )

    object: Mapped["Member"] = relationship(
        "Member",
        foreign_keys=[object_id],
        back_populates="matches_as_object"
    )

    # 1. The actual column in the database to store the ID
    # We make it nullable because a new match has no messages yet.
    last_message_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("message.id", use_alter=True,
                   name="fk_matching_last_message")
    )

    # 2. The Relationship object (Python side)
    last_message: Mapped["Message"] = relationship(
        "Message",
        # <--- CRITICAL: Tells SA to use THIS column, not the one in Message
        foreign_keys=[last_message_id],
        post_update=True                 # Helps prevent circular dependency errors during saves
    )

    # Your normal relationship to get all messages
    messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="matching",
        foreign_keys="Message.matching_id",
        order_by="Message.timestamp"
    )

    proposals: Mapped[List["DateProposal"]] = relationship(
        back_populates="matching",
        order_by="desc(DateProposal.created_at)"
    )

    @property
    def pending_proposal(self):
        """Returns the single pending proposal, or None."""
        return next((p for p in self.proposals if p.status is ProposalStatus.PENDING), None)

    @property
    def confirmed_proposal(self):
        """Returns the single confirmed proposal, or None."""
        return next((p for p in self.proposals if p.status is ProposalStatus.CONFIRMED), None)

    @property
    def ui_proposal(self):
        """
        Determines which proposal the UI should care about.
        Priority: Pending > Confirmed > None
        """
        return self.pending_proposal or self.confirmed_proposal

    def get_user(self, current_user_id: int):
        """
        Returns the User object of the partner given a current_user_id.
        """
        if self.subject_id == current_user_id:
            return self.subject
        elif self.object_id == current_user_id:
            return self.object
        else:
            # Optional: Handle case where user is not part of this match
            raise ValueError(
                f"User {current_user_id} is not in this matching.")

    def get_partner(self, current_user_id: int):
        """
        Returns the User object of the partner given a current_user_id.
        """
        if self.subject_id == current_user_id:
            return self.object
        elif self.object_id == current_user_id:
            return self.subject
        else:
            # Optional: Handle case where user is not part of this match
            raise ValueError(
                f"User {current_user_id} is not in this matching.")

    def get_grading(self, current_user_id):
        if self.subject_id == current_user_id:
            return self.obj_grading_metric
        elif self.object_id == current_user_id:
            return self.grading_metric
        else:
            # Optional: Handle case where user is not part of this match
            raise ValueError(
                f"User {current_user_id} is not in this matching.")


class Message(Base):
    __tablename__ = "message"
    id: Mapped[int] = mapped_column(primary_key=True)
    content: Mapped[str]
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    read_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True))

    user_id: Mapped[int] = mapped_column(ForeignKey("member.id"))
    matching_id: Mapped[int] = mapped_column(ForeignKey("matching.id"))
    is_system_notification: Mapped[bool] = mapped_column(default=False)

    user: Mapped["Member"] = relationship()
    matching: Mapped["Matching"] = relationship(
        "Matching",
        back_populates="messages",
        foreign_keys=[matching_id]
    )

    is_notified: Mapped[Optional[bool]]

    @property
    def receiver_id(self):
        return self.matching.get_partner(self.user_id).id


class DateProposal(Base):
    __tablename__ = "date_proposal"

    id: Mapped[int] = mapped_column(primary_key=True)
    matching_id: Mapped[int] = mapped_column(
        ForeignKey("matching.id"), nullable=False)
    proposer_id: Mapped[int] = mapped_column(
        ForeignKey("member.id"), nullable=False)
    restaurant_name: Mapped[str] = mapped_column(nullable=False)
    proposed_datetime: Mapped[datetime] = mapped_column(nullable=False)
    booker_role: Mapped[str] = mapped_column(default="none")
    updated_at: Mapped[datetime] = mapped_column(
        onupdate=datetime.now, default=datetime.now)

    status: Mapped[ProposalStatus] = mapped_column(
        SAEnum(
            ProposalStatus,
            native_enum=False,
            values_callable=lambda x: [e.value for e in x]
        ),
        default=ProposalStatus.PENDING
    )

    created_at: Mapped[datetime] = mapped_column(default=datetime.now)

    matching: Mapped["Matching"] = relationship(
        back_populates="proposals"
    )

    proposer: Mapped["Member"] = relationship(
        "Member",
        foreign_keys=[proposer_id]
    )

    is_pending_notified: Mapped[Optional[bool]]
    is_confirmed_notified: Mapped[Optional[bool]]

    @property
    def is_pending(self):
        return self.status is ProposalStatus.PENDING

    @property
    def is_confirmed(self):
        return self.status is ProposalStatus.CONFIRMED

    @property
    def is_deleted(self):
        return self.status is ProposalStatus.DELETED

    def confirm(self):
        self.status = ProposalStatus.CONFIRMED

    def delete(self):
        self.status = ProposalStatus.DELETED

    @property
    def who_reservation(self):
        if self.booker_role == 'me':
            return self.proposer_id
        elif self.booker_role == 'partner':
            return self.matching.get_partner(self.proposer_id)
        else:
            return None


class Invite(Base):
    __tablename__ = "invite"

    id: Mapped[int] = mapped_column(primary_key=True)
    token: Mapped[str] = mapped_column(unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
    expires_at: Mapped[datetime]
    used_at: Mapped[Optional[datetime]]
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("member.id"), nullable=True)

    @property
    def is_valid(self) -> bool:
        if self.used_at is not None:
            return False
        exp = self.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) <= exp


class GroupMembership(Base):
    """One row per (member, group_session) pair. Replaces the old group_members M2M table."""
    __tablename__ = "group_membership"

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("group_matching.id"), index=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("member.id"), index=True)
    joined_at: Mapped[datetime] = mapped_column(default=datetime.now)

    session_avatar: Mapped[Optional[str]]  # emoji from COMPANION_AVATARS pool

    # Ghost-detection counters (updated as messages arrive, evaluated at day 15)
    message_count: Mapped[int] = mapped_column(default=0)
    clicked_wish_button: Mapped[bool] = mapped_column(default=False)

    # Set at day-15 close
    final_label: Mapped[Optional[MemberSessionLabel]] = mapped_column(
        SAEnum(MemberSessionLabel, native_enum=False, values_callable=lambda x: [e.value for e in x]),
        nullable=True,
    )

    # Referral tracking (閨蜜/兄弟 pull-in)
    is_referral: Mapped[bool] = mapped_column(default=False)
    referred_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("member.id"))

    group: Mapped["GroupMatching"] = relationship(
        "GroupMatching", back_populates="memberships", foreign_keys=[group_id]
    )
    member: Mapped["Member"] = relationship(
        "Member", back_populates="group_memberships", foreign_keys=[member_id]
    )
    referrer: Mapped[Optional["Member"]] = relationship(
        "Member", foreign_keys=[referred_by_id]
    )

    @property
    def is_ghost(self) -> bool:
        return self.message_count == 0 and not self.clicked_wish_button


class GroupMatching(Base):
    __tablename__ = "group_matching"
    id: Mapped[int] = mapped_column(primary_key=True)
    cool_name: Mapped[Optional[str]]
    status: Mapped[GroupMatchingStatus] = mapped_column(
        SAEnum(
            GroupMatchingStatus,
            native_enum=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        default=GroupMatchingStatus.ACTIVE,
    )
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
    expires_at: Mapped[Optional[datetime]]  # created_at + 15 days, set on formation
    is_notified: Mapped[bool] = mapped_column(default=False)

    # Grouping metadata
    region: Mapped[Optional[str]]  # e.g. "北區", "中區", "南區"
    source_campaign: Mapped[Optional[str]]  # slug from campaigns.py; None = general pool
    opener_member_id: Mapped[Optional[int]] = mapped_column(ForeignKey("member.id"))
    opener: Mapped[Optional["Member"]] = relationship(foreign_keys=[opener_member_id])

    # Phase 2 summary (set when any member submits the summary form)
    meet_location: Mapped[Optional[str]]
    meet_time: Mapped[Optional[datetime]]
    meet_notes: Mapped[Optional[str]]
    summary_submitted_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("member.id"))
    summary_submitted_by: Mapped[Optional["Member"]] = relationship(
        foreign_keys=[summary_submitted_by_id]
    )

    # Phase 3: track whether 24-hr reminder was sent
    meetup_reminder_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    @property
    def has_summary(self) -> bool:
        return self.meet_time is not None

    last_message_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("group_message.id", use_alter=True, name="fk_group_matching_last_message")
    )
    last_message: Mapped[Optional["GroupMessage"]] = relationship(
        foreign_keys="GroupMatching.last_message_id", post_update=True
    )

    memberships: Mapped[list["GroupMembership"]] = relationship(
        "GroupMembership",
        foreign_keys="GroupMembership.group_id",
        back_populates="group",
        cascade="all, delete-orphan",
    )

    @property
    def members(self) -> list["Member"]:
        return [gm.member for gm in self.memberships]

    messages: Mapped[list["GroupMessage"]] = relationship(
        "GroupMessage",
        back_populates="group",
        foreign_keys="GroupMessage.group_id",
        order_by="GroupMessage.timestamp",
        cascade="all, delete-orphan",
    )
    proposals: Mapped[list["GroupDateProposal"]] = relationship(
        "GroupDateProposal",
        back_populates="group",
        order_by="desc(GroupDateProposal.created_at)",
    )

    @property
    def is_draft(self):
        return self.status is GroupMatchingStatus.DRAFT

    @property
    def is_active(self):
        return self.status is GroupMatchingStatus.ACTIVE

    @property
    def is_feedback(self):
        return self.status is GroupMatchingStatus.FEEDBACK

    @property
    def is_closed(self):
        return self.status is GroupMatchingStatus.CLOSED

    @property
    def is_cancelled(self):
        return self.status is GroupMatchingStatus.CANCELLED

    @property
    def active_proposals(self):
        return [p for p in self.proposals if not p.is_deleted]

    def approve_draft(self):
        """Promote a DRAFT group to ACTIVE, reset notification flag and restart the 15-day clock."""
        self.status = GroupMatchingStatus.ACTIVE
        self.is_notified = False
        self.expires_at = datetime.now() + timedelta(days=15)


class GroupMessage(Base):
    __tablename__ = "group_message"
    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("group_matching.id"))
    sender_id: Mapped[int] = mapped_column(ForeignKey("member.id"))
    content: Mapped[str]
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    is_notified: Mapped[Optional[bool]]
    is_system_notification: Mapped[bool] = mapped_column(default=False)

    sender: Mapped["Member"] = relationship(foreign_keys=[sender_id])
    group: Mapped["GroupMatching"] = relationship(
        "GroupMatching", back_populates="messages", foreign_keys=[group_id]
    )


class GroupDateProposal(Base):
    __tablename__ = "group_date_proposal"
    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("group_matching.id"))
    proposer_id: Mapped[int] = mapped_column(ForeignKey("member.id"))
    restaurant_name: Mapped[str]
    proposed_datetime: Mapped[datetime]
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
    is_deleted: Mapped[bool] = mapped_column(default=False)
    is_notified: Mapped[Optional[bool]]

    group: Mapped["GroupMatching"] = relationship(back_populates="proposals")
    proposer: Mapped["Member"] = relationship(foreign_keys=[proposer_id])


class GroupBadge(Base):
    """Anonymous Phase-4 badge sent from one member to another after a session meetup."""
    __tablename__ = "group_badge"

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("group_matching.id"), index=True)
    from_member_id: Mapped[int] = mapped_column(ForeignKey("member.id"))
    to_member_id: Mapped[int] = mapped_column(ForeignKey("member.id"))
    badge_type: Mapped[BadgeType] = mapped_column(
        SAEnum(BadgeType, native_enum=False, values_callable=lambda x: [e.value for e in x])
    )
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)

    group: Mapped["GroupMatching"] = relationship(foreign_keys=[group_id])
    from_member: Mapped["Member"] = relationship(foreign_keys=[from_member_id])
    to_member: Mapped["Member"] = relationship(foreign_keys=[to_member_id])


class LeadSubmissionStatus(enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class LeadSubmission(Base):
    __tablename__ = "lead_submission"

    id: Mapped[int] = mapped_column(primary_key=True)
    meta_lead_id: Mapped[str] = mapped_column(unique=True, index=True)
    name: Mapped[Optional[str]]
    phone_number: Mapped[Optional[str]]
    gender: Mapped[Optional[str]]
    age: Mapped[Optional[int]]
    line_id: Mapped[Optional[str]]
    raw_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    status: Mapped[LeadSubmissionStatus] = mapped_column(
        SAEnum(LeadSubmissionStatus, native_enum=False, values_callable=lambda x: [e.value for e in x]),
        default=LeadSubmissionStatus.PENDING,
    )
    submitted_at: Mapped[datetime]
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
    converted_member_id: Mapped[Optional[int]] = mapped_column(ForeignKey("member.id"), nullable=True)
    converted_member: Mapped[Optional["Member"]] = relationship(foreign_keys=[converted_member_id])


class Tag(Base):
    __tablename__ = 'tag'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True, index=True)
    color: Mapped[str] = mapped_column(default='secondary')
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey('member.id'), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
    members: Mapped[list['Member']] = relationship('Member', secondary=member_tag, back_populates='tags')


class UserMatchScore(Base):
    __tablename__ = 'user_match_scores'

    # Composite Primary Key: One score per pair of users
    source_user_id: Mapped[int] = mapped_column(
        ForeignKey('member.id'), primary_key=True)
    target_user_id: Mapped[int] = mapped_column(
        ForeignKey('member.id'), primary_key=True)

    score: Mapped[float]

    # Audit fields
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now())

    # Optional: Store WHY they got this score?
    # useful for debugging: {"hobbies": +10, "height": -5}
    breakdown: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=True)


