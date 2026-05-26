from datetime import date

from sqlalchemy import or_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from form_app.models import Matching, MatchingStatus, UserMatchScore
from form_app.services.cool_name import generate_funny_name


def generate_weekly_matches(users, session: Session):
    """
    Maximum-cardinality weighted matching.

    Guarantees that every eligible user who has been unmatched for ≥1 week gets
    paired if a valid partner exists (no hard excludes either way, never
    previously matched together).  Within that constraint, longer-waiting users
    still tend to get higher-quality matches because the edge weight encodes
    both combined score and wait-time, and NetworkX maximises weight when
    multiple maximum-cardinality matchings exist.

    Edge weight = combined_score + (weeks_A + weeks_B) * 10
    The wait-time bonus is large enough that pairing two long-waiting users is
    always preferred over pairing one long-waiting user with a fresh one at the
    cost of leaving the other long-waiting user unmatched.
    """
    import networkx as nx

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

    historical_pairs: set[tuple[int, int]] = set()
    last_match_date: dict[int, date | None] = {u.id: None for u in users}
    for sub, obj, created_at in existing:
        historical_pairs.add((sub, obj))
        historical_pairs.add((obj, sub))
        dt = created_at.date() if hasattr(created_at, 'date') else created_at
        for uid in (sub, obj):
            if uid in last_match_date:
                prev = last_match_date[uid]
                if prev is None or dt > prev:
                    last_match_date[uid] = dt

    # Members with a current ACTIVE matching must not receive a new draft pair
    active_rows = session.query(
        Matching.subject_id, Matching.object_id
    ).filter(
        Matching.status == MatchingStatus.ACTIVE,
        or_(
            Matching.subject_id.in_(user_ids),
            Matching.object_id.in_(user_ids),
        )
    ).all()
    active_member_ids: set[int] = {uid for sub, obj in active_rows for uid in (sub, obj)}

    today = date.today()
    weeks_unmatched: dict[int, int] = {
        uid: (9999 if last_match_date[uid] is None
              else max(0, (today - last_match_date[uid]).days // 7))
        for uid in user_ids
    }

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

    # Build a bipartite graph.  Only add edges where:
    #   - both mutual scores are positive (no hard excludes either way)
    #   - the pair has never been matched before
    #   - at least one side has been unmatched for ≥1 week (otherwise neither
    #     wants to be matched this cycle)
    G = nx.Graph()
    for male in male_users:
        for female in female_users:
            if male.id in active_member_ids or female.id in active_member_ids:
                continue
            if (male.id, female.id) in historical_pairs:
                continue
            s_mf = score_map.get((male.id, female.id), 0)
            s_fm = score_map.get((female.id, male.id), 0)
            if s_mf <= 0 or s_fm <= 0:
                continue
            w_m = weeks_unmatched[male.id]
            w_f = weeks_unmatched[female.id]
            if w_m < 1 and w_f < 1:
                continue  # both matched recently — skip this cycle
            combined = (s_mf + s_fm) / 2
            weight = combined + (w_m + w_f) * 10
            G.add_edge(f'm_{male.id}', f'f_{female.id}', weight=weight)

    # maxcardinality=True: maximise number of pairs first, then maximise weight.
    matched = nx.max_weight_matching(G, maxcardinality=True)

    final_edges: list[tuple[int, int]] = []
    for a, b in matched:
        # Nodes are labelled 'm_<id>' / 'f_<id>'
        male_node  = a if a.startswith('m_') else b
        female_node = b if b.startswith('f_') else a
        male_id   = int(male_node[2:])
        female_id = int(female_node[2:])
        final_edges.append((male_id, female_id))

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
