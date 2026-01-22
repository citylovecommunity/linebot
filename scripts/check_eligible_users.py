from config import SessionFactory


from shared.matching.scoring import (get_eligible_matching_pool,)

with SessionFactory() as session:
    eligible_members = get_eligible_matching_pool(session)
    print(len(eligible_members))
