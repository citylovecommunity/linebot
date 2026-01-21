from config import SessionFactory

from shared.matching.matching import generate_weekly_matches, match
from shared.matching.scoring import (get_eligible_matching_pool,
                                     run_matching_score_optimized)

if __name__ == '__main__':
    with SessionFactory() as session:
        eligible_members = get_eligible_matching_pool(session)
        run_matching_score_optimized(eligible_members, session)
        matchings = generate_weekly_matches(eligible_members, session)
        for matching in matchings:
            match(matching[0], matching[1], session)
