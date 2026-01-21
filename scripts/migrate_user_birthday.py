import os

from dotenv import load_dotenv
from sqlalchemy import select

from shared.database.session_maker import get_session_factory
from shared.database.models import Member


load_dotenv()


SessionFactory = get_session_factory(os.getenv("DB"))

with SessionFactory() as session:
    stmt = select(Member)
    for member in session.scalars(stmt):
        member.birthday = member.user_info['您的出生年月日']

    session.commit()
