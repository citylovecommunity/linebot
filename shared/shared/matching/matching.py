import math

import networkx as nx
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from shared.cool_name import generate_funny_name
from shared.database.models import Matching, UserMatchScore


def generate_weekly_matches(users, session: Session):
    # --- PRE-FETCHING DATA (Optimize N+1 Problem) ---

    user_ids = [u.id for u in users]

    # 2. Fetch ALL existing matches involving these users in one go
    # We want a set of pairs that are ALREADY matched to exclude them.
    existing_matches_query = session.query(Matching.subject_id, Matching.object_id).filter(
        or_(
            Matching.subject_id.in_(user_ids),
            Matching.object_id.in_(user_ids)
        )
    ).all()

    # Create a lookup set for O(1) access.
    # Store both (A,B) and (B,A) to make checking easy.
    matched_pairs = set()
    for sub, obj in existing_matches_query:
        matched_pairs.add((sub, obj))
        matched_pairs.add((obj, sub))

    # 3. Fetch ALL scores between these users in one go
    scores_query = session.query(
        UserMatchScore.source_user_id,
        UserMatchScore.target_user_id,
        UserMatchScore.score
    ).filter(
        UserMatchScore.source_user_id.in_(user_ids),
        UserMatchScore.target_user_id.in_(user_ids)
    ).all()

    # Create a score map: {(u_id, v_id): score}
    score_map = {}
    for src, tgt, score in scores_query:
        score_map[(src, tgt)] = score

    # --- GRAPH CONSTRUCTION ---

    G = nx.Graph()
    CARDINALITY_BIAS = 10000

    for i, u in enumerate(users):
        # Optimization: j starts at i+1 to avoid checking (A,B) and then (B,A) again
        for j in range(i + 1, len(users)):
            v = users[j]

            # 1. Check if they are already matched (O(1) lookup)
            if (u.id, v.id) in matched_pairs:
                continue

            # 2. Get scores from dictionary (O(1) lookup)
            # Default to 0 or a low number if they haven't rated each other
            s_u_v = score_map.get((u.id, v.id), 0)
            s_v_u = score_map.get((v.id, u.id), 0)

            # 3. Dealbreaker check (optional but recommended)
            # If they barely know each other (score 0), don't force a match
            if s_u_v <= 0 or s_v_u <= 0:
                continue

            # 4. Calculate Weight
            geo_mean = math.sqrt(s_u_v * s_v_u)
            final_weight = geo_mean + CARDINALITY_BIAS

            G.add_edge(u.id, v.id, weight=final_weight)

    # --- ALGORITHM EXECUTION ---

    # Returns set of edges: {(id1, id2), (id3, id4)}
    matching_ids = nx.max_weight_matching(G, maxcardinality=True)

    return matching_ids


def match(subject_id, object_id, session: Session):

    sub_view_score = session.query(UserMatchScore).filter(
        UserMatchScore.source_user_id == subject_id,
        UserMatchScore.target_user_id == object_id
    ).first()

    obj_view_score = session.query(UserMatchScore).filter(
        UserMatchScore.source_user_id == object_id,
        UserMatchScore.target_user_id == subject_id
    ).first()

    # 3. Create the object
    new_match = Matching(
        subject_id=subject_id,
        object_id=object_id,
        cool_name=generate_funny_name(),
        grading_metric=sub_view_score.score,
        obj_grading_metric=obj_view_score.score,
    )
    session.add(new_match)

    # 4. Conditional Commit
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        print("Race condition detected: Match already exists.")
        return None
    except Exception as e:
        session.rollback()
        raise e

    return new_match
