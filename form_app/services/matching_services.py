from database import get_db
from sqlalchemy import func

from shared.database.models import Matching, Matching_State_History, Member
from flask import render_template


def get_matching_info_from_token(token) -> Matching:
    db = get_db()
    matching = db.query(Matching).filter(
        Matching.access_token == token).first()
    return matching


def error_page(msg, header):
    return render_template('thank_you.html',
                           message=msg,
                           header=header)


def get_introduction_link(member: Member):
    return member.user_info.get('會員介紹頁網址')


def get_blind_introduction_link(member: Member):
    return member.user_info.get('盲約介紹卡一')


def get_proper_name(name, gender):
    surname = '先生' if gender == 'M' else '小姐'
    return name[0] + surname


def change_state(correct_state: str | tuple[str, ...],
                 new_state: str,
                 matching: Matching):
    """
    Refactored change_state using SQLAlchemy ORM.
    """
    session = get_db()
    # 1. Fetch the object
    # session.get is the modern way to fetch by PK in SQLAlchemy 2.0

    # 2. Validate State
    # We access the attribute directly instead of querying for it
    current_state = matching.current_state

    if isinstance(correct_state, tuple):
        if current_state not in correct_state:
            raise ValueError(
                f"Invalid state: Expected one of {correct_state}, got {current_state}")
    elif current_state != correct_state:
        raise ValueError(
            f"Invalid state: Expected {correct_state}, got {current_state}")

    # 3. Update Matching (The Update Logic)
    # SQLAlchemy tracks these changes and generates the UPDATE statement automatically on commit
    matching.current_state = new_state
    # OR datetime.now() if you prefer Python time
    matching.last_change_state_at = func.now()
    matching.updated_at = func.now()

    # 4. Insert History (The Insert Logic)
    history = Matching_State_History(
        matching_id=matching.id,
        old_state=current_state,
        new_state=new_state,
        created_at=func.now()
    )
    session.add(history)
