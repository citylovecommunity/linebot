from datetime import date, datetime, time
from typing import Any, Dict, List, Optional

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql.json import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Member(Base):
    __tablename__ = "member"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    gender: Mapped[str]
    phone_number: Mapped[str]
    is_active: Mapped[bool]
    is_test: Mapped[bool]
    email: Mapped[str]
    id_card_no: Mapped[str]
    fill_form_at: Mapped[datetime]
    user_info: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=True)

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
    created_at: Mapped[datetime]
    book_phone: Mapped[str]
    book_name: Mapped[str]
    book_time: Mapped[time]
    city: Mapped[str]
    updated_at: Mapped[datetime]
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
    status: Mapped[str] = mapped_column(default="pending")
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    matching: Mapped["Matching"] = relationship(
        "Matching",
        foreign_keys=[matching_id],
        backref="date_proposals"
    )
    proposer: Mapped["Member"] = relationship(
        "Member",
        foreign_keys=[proposer_id]
    )
