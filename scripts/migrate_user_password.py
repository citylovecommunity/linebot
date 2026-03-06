import os

from dotenv import load_dotenv
from sqlalchemy import select

from form_app.database import get_session_factory
from form_app.models import Member
from form_app.services.security import hash_password

load_dotenv()


SessionFactory = get_session_factory(os.getenv("PROD_DB_URL"))

with SessionFactory() as session:
    stmt = select(Member).where(Member.password_hash.is_(None))
    members = session.scalars(stmt).all()
    updated = 0
    skipped = 0
    for member in members:
        if not member.birthday:
            print(f"SKIP {member.name} ({member.phone_number}): no birthday")
            skipped += 1
            continue
        member.password_hash = hash_password(member.birthday.strftime('%Y%m%d'))
        print(f"SET  {member.name} ({member.phone_number}): password = {member.birthday.strftime('%Y%m%d')}")
        updated += 1

    session.commit()
    print(f"\nDone: {updated} updated, {skipped} skipped (no birthday)")
