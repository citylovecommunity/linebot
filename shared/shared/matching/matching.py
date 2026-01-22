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

    # --- 1. BUILD THE GRAPH ---
    for i, u in enumerate(users):
        for j in range(i + 1, len(users)):
            v = users[j]

            # Skip if already matched historically
            if (u.id, v.id) in matched_pairs:
                continue

            # Get scores
            s_u_v = score_map.get((u.id, v.id), 0)
            s_v_u = score_map.get((v.id, u.id), 0)

            # Dealbreaker check
            if s_u_v <= 0 or s_v_u <= 0:
                continue

            # Calculate Weight
            geo_mean = math.sqrt(s_u_v * s_v_u)
            final_weight = geo_mean + CARDINALITY_BIAS

            G.add_edge(u.id, v.id, weight=final_weight)

    # --- 2. RUN MAX WEIGHT MATCHING (Strict 1-to-1) ---
    # Returns a set of tuples: {(id1, id2), (id3, id4)}
    matching_set = nx.max_weight_matching(G, maxcardinality=True)

    # Convert to a list so we can append leftovers later
    final_edges = list(matching_set)

    # --- 3. IDENTIFY LEFTOVERS ---
    # Create a set of all nodes currently in a match
    matched_nodes = set()
    for u_id, v_id in matching_set:
        matched_nodes.add(u_id)
        matched_nodes.add(v_id)

    # Find nodes in the graph that were NOT matched
    # Note: We use G.nodes() because if a user had 0 valid edges, they aren't in G at all
    all_graph_nodes = set(G.nodes())
    leftover_nodes = all_graph_nodes - matched_nodes

    # --- 4. GREEDY FILL (The "Throuple" Fix) ---
    for node in leftover_nodes:
        # Find the neighbor with the absolute highest weight
        # G[node].items() gives us (neighbor_id, attributes_dict)
        if not G[node]:
            continue  # Should be impossible if node is in G, but good safety

        best_neighbor = max(G[node].items(), key=lambda x: x[1]['weight'])

        target_id = best_neighbor[0]
        # weight = best_neighbor[1]['weight'] # Unused, but available if needed

        # Add this edge to our final results
        final_edges.append((node, target_id))

    return final_edges


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
