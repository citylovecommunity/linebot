"""
Check active matchings created at 2026-03-21 18:29 with no last_message_id.
Run: uv run python scripts/check_new_matchings.py
"""
from datetime import datetime

from sqlalchemy import select

from form_app.config import settings
from form_app.database import get_session_factory
from form_app.models import Matching, MatchingStatus

SessionFactory = get_session_factory(settings.DB)

with SessionFactory() as session:
    matchings = session.scalars(
        select(Matching)
        .where(
            Matching.status == MatchingStatus.ACTIVE,
            Matching.last_message_id.is_(None),
            Matching.created_at >= datetime(2026, 3, 21, 18, 29, 0),
            Matching.created_at < datetime(2026, 3, 21, 18, 30, 0),
        )
        .order_by(Matching.id)
    ).all()

    if not matchings:
        print("No matching records found.")
    else:
        print(f"Found {len(matchings)} matching(s):\n")
        print(f"{'ID':>6}  {'Subject':>22}  {'Object':>22}  {'Cool Name':>22}  {'is_match_notified':>18}  {'Created At'}")
        print("-" * 110)
        for m in matchings:
            subj = f"{m.subject.name} (#{m.subject_id})" if m.subject else f"#{m.subject_id}"
            obj  = f"{m.object.name} (#{m.object_id})"  if m.object  else f"#{m.object_id}"
            print(f"{m.id:>6}  {subj:>22}  {obj:>22}  {str(m.cool_name):>22}  {str(m.is_match_notified):>18}  {m.created_at}")
