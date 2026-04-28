from datetime import date

from sqlalchemy import or_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from form_app.models import Matching, MatchingStatus, UserMatchScore
from form_app.services.cool_name import generate_funny_name


def generate_weekly_matches(users, session: Session):
    """
    Priority greedy matching.

    1. Compute weeks since last match for every eligible user from DB history.
    2. Iterate users with >= 1 week unmatched, longest-waiting first.
       Never-matched users sort to the top.
    3. For each such user A (skip if already paired this session):
       - Candidates = opposite gender, in eligible pool, not yet paired this session,
         with a positive score from A.
       - Pick the candidate with the fewest total historical matchings.
         Tiebreak: highest score from A to that candidate.
       - Pair them; mark both as paired for the rest of this session.
    4. Users not reached as A, or never chosen as a candidate, go unmatched.
    """
    user_ids = [u.id for u in users]
    if not user_ids:
        return []

    # Fetch all existing non-draft matchings involving these users
    existing = session.query(
        Matching.subject_id, Matching.object_id, Matching.created_at
    ).filter(
        Matching.status != MatchingStatus.DRAFT,
        or_(
            Matching.subject_id.in_(user_ids),
            Matching.object_id.in_(user_ids),
        )
    ).all()

    # Historical match count per user + set of previously matched pairs
    match_count: dict[int, int] = {u.id: 0 for u in users}
    historical_pairs: set[tuple[int, int]] = set()
    for sub, obj, _ in existing:
        if sub in match_count:
            match_count[sub] += 1
        if obj in match_count:
            match_count[obj] += 1
        historical_pairs.add((sub, obj))
        historical_pairs.add((obj, sub))

    # Most recent matching date per user → weeks unmatched
    last_match_date: dict[int, date | None] = {u.id: None for u in users}
    for sub, obj, created_at in existing:
        dt = created_at.date() if hasattr(created_at, 'date') else created_at
        for uid in (sub, obj):
            if uid in last_match_date:
                prev = last_match_date[uid]
                if prev is None or dt > prev:
                    last_match_date[uid] = dt

    today = date.today()
    weeks_unmatched: dict[int, int] = {}
    for uid in user_ids:
        ld = last_match_date[uid]
        # Never-matched users get a large sentinel so they sort to the top
        weeks_unmatched[uid] = 9999 if ld is None else max(0, (today - ld).days // 7)

    # Batch-fetch scores between all eligible users
    scores = session.query(
        UserMatchScore.source_user_id,
        UserMatchScore.target_user_id,
        UserMatchScore.score,
    ).filter(
        UserMatchScore.source_user_id.in_(user_ids),
        UserMatchScore.target_user_id.in_(user_ids),
    ).all()

    score_map: dict[tuple[int, int], float] = {
        (r.source_user_id, r.target_user_id): r.score for r in scores
    }

    male_users = [u for u in users if u.gender == 'M']
    female_users = [u for u in users if u.gender == 'F']

    # Only users unmatched for at least one week are initiators
    initiators = sorted(
        [u for u in users if weeks_unmatched[u.id] >= 1],
        key=lambda u: weeks_unmatched[u.id],
        reverse=True,
    )

    paired: set[int] = set()
    final_edges: list[tuple[int, int]] = []

    for user in initiators:
        if user.id in paired:
            continue

        opposite = female_users if user.gender == 'M' else male_users

        candidates = []
        for candidate in opposite:
            if candidate.id in paired:
                continue
            if (user.id, candidate.id) in historical_pairs:
                continue
            s_forward = score_map.get((user.id, candidate.id), 0)
            s_reverse = score_map.get((candidate.id, user.id), 0)
            if s_forward <= 0 or s_reverse <= 0:
                continue
            candidates.append((candidate, match_count[candidate.id], s_forward))

        if not candidates:
            continue

        # Primary sort: fewest historical matchings. Tiebreak: highest score from user → candidate.
        best_candidate, _, _ = min(candidates, key=lambda x: (x[1], -x[2]))

        male_id, female_id = (
            (user.id, best_candidate.id) if user.gender == 'M'
            else (best_candidate.id, user.id)
        )
        final_edges.append((male_id, female_id))
        paired.add(user.id)
        paired.add(best_candidate.id)

    return final_edges


def update_unmatched_counters(eligible_members, matched_ids: set[int], session: Session):
    """
    Call when a cycle is finalised (draft approved or direct run).
    Resets the counter for anyone matched; increments others.
    Never call during draft generation — delete+regenerate must not count.
    """
    for member in eligible_members:
        if member.id in matched_ids:
            member.consecutive_unmatched_weeks = 0
        else:
            member.consecutive_unmatched_weeks = (member.consecutive_unmatched_weeks or 0) + 1


def match(subject_id, object_id, session: Session):
    sub_score = session.query(UserMatchScore).filter_by(
        source_user_id=subject_id, target_user_id=object_id
    ).first()
    obj_score = session.query(UserMatchScore).filter_by(
        source_user_id=object_id, target_user_id=subject_id
    ).first()

    new_match = Matching(
        subject_id=subject_id,
        object_id=object_id,
        cool_name=generate_funny_name(),
        grading_metric=sub_score.score,
        obj_grading_metric=obj_score.score,
    )
    session.add(new_match)
    return new_match


def process_matches_bulk(eligible_members, session: Session, is_draft: bool = False):
    matchings = generate_weekly_matches(eligible_members, session)

    if not is_draft:
        matched_ids: set[int] = {uid for pair in matchings for uid in pair}
        update_unmatched_counters(eligible_members, matched_ids, session)

    if not matchings:
        return

    involved_ids = {uid for pair in matchings for uid in pair}
    raw_scores = session.query(UserMatchScore).filter(
        UserMatchScore.source_user_id.in_(involved_ids),
        UserMatchScore.target_user_id.in_(involved_ids),
    ).all()
    score_map = {(s.source_user_id, s.target_user_id): s.score for s in raw_scores}

    matches_to_insert = []
    for subject_id, object_id in matchings:
        sub_score = score_map.get((subject_id, object_id))
        obj_score = score_map.get((object_id, subject_id))
        if sub_score is None or obj_score is None:
            continue

        row = {
            "subject_id": subject_id,
            "object_id": object_id,
            "cool_name": generate_funny_name(),
            "grading_metric": sub_score,
            "obj_grading_metric": obj_score,
        }
        if is_draft:
            row["status"] = MatchingStatus.DRAFT.value
            row["is_match_notified"] = True
        matches_to_insert.append(row)

    if matches_to_insert:
        stmt = insert(Matching).values(matches_to_insert)
        session.execute(stmt)
