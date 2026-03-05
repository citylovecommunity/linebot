"""
Backfills expiration_date on Member rows where it is NULL,
computed as fill_form_at + membership_months months.

Only fills NULL values — existing data is never overwritten.

Run with:
    uv run python scripts/backfill_expiration_date.py
"""
from sqlalchemy import select

from dateutil.relativedelta import relativedelta
from form_app.config import settings
from form_app.database import get_session_factory
from form_app.models import Member

SessionFactory = get_session_factory(settings.DB)

with SessionFactory() as session:
    members = session.scalars(
        select(Member).where(Member.expiration_date == None)
    ).all()

    print(f"Found {len(members)} members without expiration_date.")

    updated = 0
    skipped = 0
    for member in members:
        months = member.membership_months
        if months is None or not member.fill_form_at:
            skipped += 1
            continue
        member.expiration_date = (member.fill_form_at + relativedelta(months=months)).date()
        updated += 1
        print(f"  [{member.id}] {member.name}: {member.expiration_date} ({months}月)")

    session.commit()
    print(f"\nDone. Updated {updated}, skipped {skipped} (no plan data).")
