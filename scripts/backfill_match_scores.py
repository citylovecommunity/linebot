"""
Backfills grading_metric / obj_grading_metric on Matching rows where both are 0.

For each such matching:
  1. Look up pre-computed scores in user_match_scores.
  2. If missing, compute on-the-fly from user_info and persist to user_match_scores.
  3. Update the matching row.

Run with:
    uv run python scripts/backfill_match_scores.py
"""
from sqlalchemy import and_, select

from form_app.config import settings
from form_app.database import get_session_factory
from form_app.models import Matching, Member, UserMatchScore
from form_app.services.scoring import UserProfileAdapter, calculate_match_score

SessionFactory = get_session_factory(settings.DB)


def get_or_compute_score(session, source: Member, target: Member) -> float:
    record = session.query(UserMatchScore).filter(
        UserMatchScore.source_user_id == source.id,
        UserMatchScore.target_user_id == target.id,
    ).first()

    if record:
        return record.score

    score, breakdown = calculate_match_score(
        UserProfileAdapter(source.user_info or {}),
        UserProfileAdapter(target.user_info or {}),
    )
    session.add(UserMatchScore(
        source_user_id=source.id,
        target_user_id=target.id,
        score=score,
        breakdown=breakdown,
    ))
    return score


with SessionFactory() as session:
    zero_matchings = session.scalars(
        select(Matching).where(
            and_(Matching.grading_metric == 0, Matching.obj_grading_metric == 0)
        )
    ).all()

    print(f"Found {len(zero_matchings)} matchings with 0/0 scores.")

    updated = 0
    for matching in zero_matchings:
        subject = session.get(Member, matching.subject_id)
        obj = session.get(Member, matching.object_id)

        if subject is None or obj is None:
            print(f"  [matching {matching.id}] skipped — member not found")
            continue

        sub_score = get_or_compute_score(session, subject, obj)
        obj_score = get_or_compute_score(session, obj, subject)

        matching.grading_metric = int(sub_score)
        matching.obj_grading_metric = int(obj_score)
        updated += 1
        print(f"  [matching {matching.id}] {matching.cool_name}: "
              f"{subject.name} → {int(sub_score)}, {obj.name} → {int(obj_score)}")

    session.commit()
    print(f"\nDone. Updated {updated} / {len(zero_matchings)} matchings.")
