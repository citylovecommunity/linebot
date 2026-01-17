from shared.database.base import get_session_factory
from shared.database.models import Member
from shared.security import hash_password
from dotenv import load_dotenv
from sqlalchemy import select
import os


load_dotenv()


SessionFactory = get_session_factory(os.getenv("DB"))

with SessionFactory() as session:
    stmt = select(Member)
    for member in session.scalars(stmt):
        member.password_hash = hash_password(member.id_card_no)

    session.commit()
