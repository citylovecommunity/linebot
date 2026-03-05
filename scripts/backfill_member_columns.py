"""
Backfills missing birthday, rank, marital_status, and password_hash
columns on Member rows by extracting values from user_info JSONB.

Only fills NULL values — existing data is never overwritten.
"""
import os
from datetime import datetime

from form_app.config import settings
from sqlalchemy import or_, select

from form_app.database import get_session_factory
from form_app.models import Member
from form_app.services.security import hash_password


SessionFactory = get_session_factory(settings.DB)


def parse_birthday(raw: str):
    """Converts '1990/05/20' -> date(1990, 5, 20)."""
    if not raw:
        return None
    try:
        return datetime.strptime(raw.strip(), "%Y/%m/%d").date()
    except ValueError:
        return None


with SessionFactory() as session:
    # Only fetch members that are missing at least one target column.
    stmt = select(Member).where(
        or_(
            Member.birthday == None,
            Member.rank == None,
            Member.marital_status == None,
            Member.password_hash == None,
        )
    )

    members = session.scalars(stmt).all()
    print(f"Found {len(members)} members with missing data.")

    updated = 0
    for member in members:
        info = member.user_info or {}
        changed = False

        # --- birthday ---
        if member.birthday is None:
            birthday = parse_birthday(info.get("您的出生年月日"))
            if birthday:
                member.birthday = birthday
                changed = True

        # --- rank ---
        if member.rank is None:
            rank = info.get("排約等級一")
            if rank:
                member.rank = rank
                changed = True

        # --- marital_status ---
        if member.marital_status is None:
            marital = info.get("您目前的感情狀況")
            if marital:
                member.marital_status = marital
                changed = True

        # --- password_hash ---
        if member.password_hash is None:
            # Use the now-resolved birthday (either just set or already on the object).
            bday = member.birthday
            if bday:
                member.password_hash = hash_password(bday.strftime("%Y%m%d"))
                changed = True

        if changed:
            updated += 1
            print(f"  [{member.id}] {member.name} — updated")

    session.commit()
    print(f"\nDone. Updated {updated} / {len(members)} members.")
