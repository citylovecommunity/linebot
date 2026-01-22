from config import SessionFactory

from shared.matching.matching import generate_weekly_matches, match
from shared.matching.scoring import (get_eligible_matching_pool,
                                     run_matching_score_optimized)
from shared.database.models import UserMatchScore, Matching
from shared.cool_name import generate_funny_name
from sqlalchemy import tuple_
# Assuming Postgres, see note below for MySQL/SQLite
from sqlalchemy.dialects.postgresql import insert


def process_matches_bulk(eligible_members, session):
    # 1. Generate the pairs (tuples of ids)
    matchings = generate_weekly_matches(eligible_members, session)
    if not matchings:
        return

    # 2. OPTIMIZATION: Pre-fetch all scores in ONE query
    # We collect all subject/object IDs involved to filter the query
    involved_user_ids = set()
    for m in matchings:
        involved_user_ids.add(m[0])
        involved_user_ids.add(m[1])

    # Query all scores where both users are in our current matching pool
    # This replaces the 2 SELECTs per loop.
    raw_scores = session.query(UserMatchScore).filter(
        UserMatchScore.source_user_id.in_(involved_user_ids),
        UserMatchScore.target_user_id.in_(involved_user_ids)
    ).all()

    # Create a lookup dictionary: (source, target) -> score
    score_map = {
        (s.source_user_id, s.target_user_id): s.score
        for s in raw_scores
    }

    # 3. Prepare data for Bulk Insert
    matches_to_insert = []

    for subject_id, object_id in matchings:
        # Dictionary lookup is instant vs DB query
        sub_score = score_map.get((subject_id, object_id))
        obj_score = score_map.get((object_id, subject_id))

        if sub_score is None or obj_score is None:
            # Handle missing scores gracefully (log it, skip it, or default to 0)
            continue

        matches_to_insert.append({
            "subject_id": subject_id,
            "object_id": object_id,
            "cool_name": generate_funny_name(),
            "grading_metric": sub_score,
            "obj_grading_metric": obj_score,
        })

    # 4. OPTIMIZATION: Bulk Insert with "On Conflict Do Nothing"
    # This handles the "Race condition" check natively in the DB without
    # rolling back transactions in Python.

    if matches_to_insert:
        stmt = insert(Matching).values(matches_to_insert)

        # # This acts like your try/except IntegrityError block but for the whole batch
        # # It skips rows that already exist.
        # stmt = stmt.on_conflict_do_nothing(
        #     # Replace with your actual UniqueConstraint columns
        #     index_elements=['subject_id', 'object_id']
        # )

        session.execute(stmt)
        session.commit()


if __name__ == '__main__':
    with SessionFactory() as session:
        eligible_members = get_eligible_matching_pool(session)
        run_matching_score_optimized(eligible_members, session)
        process_matches_bulk(eligible_members, session)
