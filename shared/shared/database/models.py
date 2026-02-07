
import enum
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import DateTime
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


class Base(DeclarativeBase):
    pass


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

    is_active: Mapped[bool] = mapped_column(default=True)
    updated_at: Mapped[datetime] = mapped_column(
        onupdate=datetime.now, default=datetime.now)

    birthday: Mapped[Optional[date]]

    is_test: Mapped[bool] = mapped_column(default=False)

    email: Mapped[Optional[str]]
    id_card_no: Mapped[Optional[str]]
    fill_form_at: Mapped[datetime]
    user_info: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=True)

    rank: Mapped[Optional[str]]
    marital_status: Mapped[Optional[str]]

    height: Mapped[Optional[int]]

    pref_min_height: Mapped[Optional[int]]
    pref_max_height: Mapped[Optional[int]]
    pref_oldest_birth_year: Mapped[Optional[int]]
    pref_youngest_birth_year: Mapped[Optional[int]]

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return True

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
        """Returns a combined list of matches where user is subject or object."""
        return self.matches_as_subject + self.matches_as_object

    password_hash: Mapped[Optional[str]]

    is_admin:  Mapped[Optional[bool]] = mapped_column(default=False)

    line_info: Mapped[Optional["Line_Info"]] = relationship(
        back_populates="member",
        primaryjoin="Member.phone_number == Line_Info.phone_number",
        foreign_keys="Line_Info.phone_number"
    )

    last_notification_sent_at: Mapped[Optional[datetime]] = mapped_column(
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

    @property
    def introduction_link(self):
        return self.user_info.get('會員介紹頁網址')

    @property
    def blind_introduction_link(self):
        return self.user_info.get('盲約介紹卡一')


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

    def activate(self):
        self.status = MatchingStatus.ACTIVE
        self.cancel_by_id = None

    def complete(self):
        self.status = MatchingStatus.COMPLETED

    def cancel(self, cancel_id):
        self.status = MatchingStatus.CANCELLED
        self.cancel_by_id = cancel_id

    def activate_by(self, user_id):
        """Records acceptance and activates match if both agree."""
        if user_id == self.user_a_id:
            self.subject_accepted = True
        elif user_id == self.user_b_id:
            self.object_accepted = True

        # Check if BOTH have accepted
        if self.subject_accepted and self.object_accepted:
            self.status = MatchingStatus.ACTIVE

    def has_accepted(self, user_id):
        """Helper to check if a specific user has already agreed."""
        if user_id == self.subject_id:
            return self.subject_accepted
        elif user_id == self.object_id:
            return self.object_accepted
        return False

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
        foreign_keys="Message.matching_id"
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


Member.unread_count = column_property(
    select(func.count(Message.id))
    .join(Matching, Message.matching_id == Matching.id)
    .where(
        and_(
            # Logic: Message is unread
            Message.read_at == None,

            # Logic: User is NOT the sender
            Message.user_id != Member.id,  # Refers to User.id

            # Logic: User is part of the match
            or_(Matching.subject_id == Member.id,
                Matching.object_id == Member.id)
        )
    )
    # Tells SQL to link 'id' to the outer User table
    .correlate_except(Matching)
    .scalar_subquery()
)
