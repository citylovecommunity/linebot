import math

from sqlalchemy import or_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from form_app.models import Matching, MatchingStatus, UserMatchScore
from form_app.services.cool_name import generate_funny_name

# Members unmatched for this many consecutive cycles unlock re-matching with
# historical partners so the pool doesn't shrink to nothing over time.
REMATCH_THRESHOLD = 2


def generate_weekly_matches(users, session: Session):
    """
    Greedy sequential matching — each user initiates at most one new match per
    cycle, but can appear as a candidate in multiple matches.

    Algorithm:
      1. Sort users by consecutive_unmatched_weeks DESC so long-waiting members
         get first pick of candidates.
      2. For each user not yet an initiator this cycle, find their highest-scoring
         valid candidate (opposite gender, no dealbreaker, not already paired with
         them this cycle, historical pairs allowed after REMATCH_THRESHOLD).
      3. Create the pair and mark the user as done for this cycle.
         The candidate is NOT marked done — they will get their own turn.

    This guarantees every user with at least one valid candidate gets matched,
    without exhausting the full M×F cross-product in a single cycle.
    """
    user_ids = [u.id for u in users]
    if not user_ids:
        return []

    # Fetch all existing matchings to exclude previously matched pairs
    existing = session.query(Matching.subject_id, Matching.object_id).filter(
        or_(
            Matching.subject_id.in_(user_ids),
            Matching.object_id.in_(user_ids),
        )
    ).all()

    matched_pairs: set[tuple[int, int]] = set()
    for sub, obj in existing:
        matched_pairs.add((sub, obj))
        matched_pairs.add((obj, sub))

    # Batch-fetch cross-gender scores
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

    male_users   = [u for u in users if u.gender == 'M']
    female_users = [u for u in users if u.gender == 'F']

    # Process longest-waiting members first so they get the best candidates
    sorted_users = sorted(users, key=lambda u: u.consecutive_unmatched_weeks or 0, reverse=True)

    initiated: set[int] = set()           # users who have already initiated a match
    cycle_pairs: set[tuple[int, int]] = set()  # canonical (min_id, max_id) pairs created this cycle
    final_edges: list[tuple[int, int]] = []    # (male_id, female_id)

    for user in sorted_users:
        if user.id in initiated:
            continue  # already initiated a match this cycle

        opposite = female_users if user.gender == 'M' else male_users
        u_weeks = user.consecutive_unmatched_weeks or 0

        candidates: list[tuple[object, float]] = []
        for candidate in opposite:
            # Prevent creating the same pair twice within one cycle
            pair_key = (min(user.id, candidate.id), max(user.id, candidate.id))
            if pair_key in cycle_pairs:
                continue

            # Skip historical pairs unless the re-matching threshold is met
            if (user.id, candidate.id) in matched_pairs:
                c_weeks = candidate.consecutive_unmatched_weeks or 0
                if u_weeks < REMATCH_THRESHOLD and c_weeks < REMATCH_THRESHOLD:
                    continue

            s1 = score_map.get((user.id, candidate.id), 0)
            s2 = score_map.get((candidate.id, user.id), 0)
            if s1 <= 0 or s2 <= 0:
                continue

            candidates.append((candidate, math.sqrt(s1 * s2)))

        if not candidates:
            continue

        best, _ = max(candidates, key=lambda x: x[1])

        edge = (user.id, best.id) if user.gender == 'M' else (best.id, user.id)
        final_edges.append(edge)
        initiated.add(user.id)
        cycle_pairs.add((min(user.id, best.id), max(user.id, best.id)))

    return final_edges


def update_unmatched_counters(eligible_members, matched_ids: set[int], session: Session):
    """
    Call when a cycle is finalised (draft approved or direct run).
    Resets the counter for anyone who appeared in any match; increments others.
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

    # For direct (non-draft) runs, finalise the cycle counter immediately.
    # For draft runs, update_unmatched_counters() is called on approval instead.
    if not is_draft:
        matched_ids: set[int] = {uid for pair in matchings for uid in pair}
        update_unmatched_counters(eligible_members, matched_ids, session)

    if not matchings:
        return

    # Batch-fetch scores for bulk insert
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
