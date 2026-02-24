from form_app.services.matching import match
from form_app.services.scoring import run_matching_score_optimized, get_eligible_matching_pool
from form_app.config import settings
from form_app.database import get_session_factory


session_factory = get_session_factory(settings.DB)

with session_factory() as session:
    eligible_members = get_eligible_matching_pool(session)
    run_matching_score_optimized(eligible_members, session)

    match(12016, 3436, session)
    match(12016, 6331, session)
    match(12016, 54, session)

    session.commit()
