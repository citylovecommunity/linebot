import os

from dotenv import load_dotenv
from sqlalchemy import select

from form_app.database import get_session_factory
from form_app.models import Member
from form_app.services.security import hash_password

load_dotenv()


SessionFactory = get_session_factory(os.getenv("DB"))

with SessionFactory() as session:
    stmt = select(Member)
    for member in session.scalars(stmt):
        member.password_hash = hash_password(
            member.birthday.strftime('%Y%m%d'))

    session.commit()
