import os
from dotenv import load_dotenv
from shared.database.session_maker import get_session_factory

load_dotenv()

SessionFactory = get_session_factory(os.getenv("DB"))
