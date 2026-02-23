import os
import random

from dotenv import load_dotenv
from sqlalchemy import func, select

from form_app.database import get_session_factory
from form_app.models import Matching, Member
from form_app.services.cool_name import generate_funny_name

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
