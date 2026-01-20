# weekly_matcher.py
from config import SessionFactory
from sqlalchemy import func

from shared.database.models import Member, UserMatchScore
from shared.scoring import (UserProfileAdapter, calculate_match_score,
                            get_eligible_matching_pool)


def run_weekly_matching():
    session = SessionFactory()

    # 1. Get Active Members (You might have an 'is_active' flag)
    active_users = get_eligible_matching_pool(session)
    active_ids = [u.id for u in active_users]

    for me in active_users:
        print(f"Processing matches for {me.id}...")

        # --- STAGE 1: CANDIDATE GENERATION (SQL Filter) ---
        # Find users who match my HARD requirements
        candidates = session.query(Member).filter(
            Member.id != me.id,
            Member.id.in_(active_ids),
            Member.gender != me.gender,  # Heterosexual matching assumption
            # Inscribed Age/Height Logic
            Member.height.between(me.pref_min_height, me.pref_max_height),
            func.extract('year', Member.birthday).between(
                me.pref_oldest_birth_year, me.pref_youngest_birth_year)
        )

        # Dealbreaker: Marital Status
        # If I have "離婚" in my dealbreakers list inside JSON...
        my_adapter = UserProfileAdapter(me.user_info)
        if "離婚" in my_adapter.dealbreakers:
            candidates = candidates.filter(Member.marital_status != "離婚")

        candidate_list = candidates.all()

        # --- STAGE 2: SCORING (Python) ---
        scored_results = []

        for candidate in candidate_list:
            cand_adapter = UserProfileAdapter(candidate.user_info)

            # Run the grading logic
            score, breakdown = calculate_match_score(my_adapter, cand_adapter)

            # Store the grading info
            match_record = UserMatchScore(
                source_user_id=me.id,
                target_user_id=candidate.id,
                score=score,
                breakdown=breakdown,
            )
            session.merge(match_record)  # Upsert

            # Keep in memory for sorting
            scored_results.append((score, candidate.id))

        # # --- STAGE 3: SELECTION (The "Top Pick") ---
        # # Sort by score descending
        # scored_results.sort(key=lambda x: x[0], reverse=True)

        # if scored_results:
        #     top_score, top_candidate_id = scored_results[0]

        #     # Only match if score is decent (e.g. > 50)
        #     if top_score > 50:
        #         weekly_pick = WeeklyMatch(
        #             user_id=me.id,
        #             matched_user_id=top_candidate_id,
        #             match_score=top_score,
        #             week_start_date=func.current_date()  # Or calculated start of week
        #         )
        #         session.add(weekly_pick)

    session.commit()
    print("Weekly matching complete.")


if __name__ == '__main__':
    run_weekly_matching()
