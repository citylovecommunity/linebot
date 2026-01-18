
import enum
from datetime import date, datetime, time
from typing import Any, Dict, List, Optional

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql.json import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Enum as SAEnum

from shared.database.base import Base


class ProposalStatus(enum.Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    DELETED = "DELETED"


class MatchingStatus(enum.Enum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class Member(Base):
    __tablename__ = "member"
    id: Mapped[int] = mapped_column(primary_key=True)

    def get_id(self):
        # Convert the primary key to a string
        return str(self.id)

    name: Mapped[str]
    gender: Mapped[str]
    phone_number: Mapped[str]
    is_active: Mapped[bool]
    updated_at: Mapped[datetime] = mapped_column(onupdate=datetime.now)

    is_test: Mapped[bool]

    email: Mapped[str]
    id_card_no: Mapped[str]
    fill_form_at: Mapped[datetime]
    user_info: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=True)

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

    password_hash: Mapped[str]

    is_admin:  Mapped[bool] = mapped_column(default=False)

    line_info: Mapped["Line_Info"] = relationship(back_populates="member")

    def get_proper_name(self):
        surname = '先生' if self.gender == 'M' else '小姐'
        return self.name[0] + surname

    def get_introduction_link(self):
        return self.user_info.get('會員介紹頁網址')

    def get_blind_introduction_link(self):
        return self.user_info.get('盲約介紹卡一')


class Line_Info(Base):
    __tablename__ = "line_info"
    phone_number: Mapped[str] = mapped_column(
        ForeignKey("member.phone_number"), primary_key=True)
    user_id: Mapped[str]
    member: Mapped["Member"] = relationship(back_populates="line_info")


class Matching(Base):
    __tablename__ = "matching"
    id: Mapped[int] = mapped_column(primary_key=True)
    subject_id: Mapped[int] = mapped_column(
        ForeignKey("member.id"))

    object_id: Mapped[int] = mapped_column(
        ForeignKey("member.id"))
    created_mode: Mapped[str]
    current_state: Mapped[str]

    status: Mapped[MatchingStatus] = mapped_column(
        SAEnum(
            MatchingStatus,
            native_enum=False,
            values_callable=lambda x: [e.value for e in x]
        ),
        default=MatchingStatus.PENDING
    )

    subject_accepted: Mapped[bool]
    object_accepted: Mapped[bool]

    @property
    def is_active(self):
        return self.status is MatchingStatus.ACTIVE

    @property
    def is_pending(self):
        return self.status is MatchingStatus.PENDING

    @property
    def is_completed(self):
        return self.status is MatchingStatus.COMPLETED

    @property
    def is_cancelled(self):
        return self.status is MatchingStatus.CANCELLED

    def activate(self):
        self.status = MatchingStatus.ACTIVE

    def complete(self):
        self.status = MatchingStatus.COMPLETED

    def cancel(self):
        self.status = MatchingStatus.CANCELLED

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

    access_token: Mapped[str]
    last_sent_at: Mapped[datetime]
    place1_url: Mapped[str]
    place1_name: Mapped[str]
    place1_id: Mapped[str]

    place2_url: Mapped[str]
    place2_name: Mapped[str]
    place2_id: Mapped[str]

    date1: Mapped[date]
    date2: Mapped[date]
    date3: Mapped[date]
    selected_place: Mapped[str]
    selected_date: Mapped[date]

    comment: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
    book_phone: Mapped[str]
    book_name: Mapped[str]
    book_time: Mapped[time]
    city: Mapped[str]

    updated_at: Mapped[datetime] = mapped_column(onupdate=datetime.now)

    last_change_state_at: Mapped[datetime]
    grading_metric: Mapped[int]
    obj_grading_metric: Mapped[int]
    pause: Mapped[bool]

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

    matching_state_histories: Mapped[list["Matching_State_History"]] = relationship(
        "Matching_State_History",
        foreign_keys="Matching_State_History.matching_id",
        back_populates="matching"
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


class Matching_State_History(Base):
    __tablename__ = "matching_state_history"
    id: Mapped[int] = mapped_column(primary_key=True)
    matching_id: Mapped[int] = mapped_column(ForeignKey("matching.id"))
    old_state: Mapped[str]
    new_state: Mapped[str]
    created_at: Mapped[datetime]

    matching: Mapped["Matching"] = relationship(
        "Matching", foreign_keys=matching_id, back_populates="matching_state_histories")


class Message(Base):
    __tablename__ = "message"
    id: Mapped[int] = mapped_column(primary_key=True)
    content: Mapped[str]
    timestamp: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    user_id: Mapped[int] = mapped_column(ForeignKey("member.id"))
    matching_id: Mapped[int] = mapped_column(ForeignKey("matching.id"))
    is_system_notification: Mapped[bool] = mapped_column(default=False)

    user: Mapped["Member"] = relationship()
    matching: Mapped["Matching"] = relationship(
        "Matching",
        back_populates="messages",
        foreign_keys=[matching_id]
    )


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
    updated_at: Mapped[datetime] = mapped_column(onupdate=datetime.now)

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
