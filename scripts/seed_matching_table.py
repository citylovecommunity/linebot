import os

from dotenv import load_dotenv
from sqlalchemy import select, func


from shared.database.base import get_session_factory
from shared.database.models import Member, Matching
from shared.cool_name import generate_funny_name
import random

load_dotenv()


SessionFactory = get_session_factory(os.getenv("DB"))

with SessionFactory() as session:
    random_user = session.query(Member).where(
        Member.is_active == True).order_by(func.random()).first()

    ten_others = session.query(Member).where(
        Member.is_active == True) \
        .filter(Member.id != random_user.id)\
        .filter(Member.gender != random_user.gender)\
        .order_by(func.random())\
        .limit(10)\
        .all()

    print(random_user.id)

    for user in ten_others:
        new_match = Matching(subject=random_user,
                             object=user,
                             cool_name=generate_funny_name(),
                             grading_metric=random.randint(0, 100),
                             obj_grading_metric=random.randint(0, 100),
                             )
        session.add(new_match)
    session.commit()
