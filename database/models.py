from sqlalchemy.orm import mapped_column, Mapped, relationship
from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql.json import JSONB
from datetime import datetime, time, date
from typing import List, Dict, Any
from base import Base


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
    place2_url: Mapped[str]
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


class Matching_State_History(Base):
    __tablename__ = "matching_state_history"
    id: Mapped[int] = mapped_column(primary_key=True)
    matching_id: Mapped[int] = mapped_column(ForeignKey("matching.id"))
    old_sate: Mapped[str]
    new_state: Mapped[str]
    created_at: Mapped[datetime]

    matching: Mapped["Matching"] = relationship(
        "Matching", foreign_keys=matching_id, back_populates="matching_state_histories")
