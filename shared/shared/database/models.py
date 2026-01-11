from datetime import date, datetime, time
from typing import Any, Dict, List

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

    matches_as_subject: Mapped[List["Matching"]] = relationship(
        "Matching",
        foreign_keys="[Matching.subject_id]",
        back_populates="subject"
    )

    matches_as_object: Mapped[List["Matching"]] = relationship(
        "Matching",
        foreign_keys="[Matching.object_id]",
        back_populates="object"
    )
    line_info: Mapped["Line_Info"] = relationship(back_populates="member")

    def get_proper_name(self):
        surname = '先生' if self.gender == 'M' else '小姐'
        return self.name[0] + surname


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

    matching_state_histories: Mapped[List["Matching_State_History"]] = relationship(
        "Matching_State_History",
        foreign_keys="[Matching_State_History.matching_id]",
        back_populates="matching"
    )

    messages: Mapped[List["Message"]] = relationship(
        "Message",
        foreign_keys="[Message.match_id]",
        back_populates="match"
    )

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
    match_id: Mapped[int] = mapped_column(ForeignKey("matching.id"))

    user: Mapped["Member"] = relationship("Member")
    match: Mapped["Matching"] = relationship(
        "Matching", back_populates="messages")
