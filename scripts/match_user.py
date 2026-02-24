from form_app.services.matching import match
from form_app.config import settings
from form_app.database import get_session_factory


session_factory = get_session_factory(settings.DB)

with session_factory() as session:
    match(12016, 11722, session)
    match(12016, 11722, session)
