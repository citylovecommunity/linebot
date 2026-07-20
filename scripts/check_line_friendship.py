"""
Read-only audit: for every bound Line_Info row, check whether that LINE user
is still a friend of the OA. LIFF login (used by /liff/bind) only requires
the user to be logged into LINE — it does NOT require them to have added
the OA as a friend — so some existing bindings may point at users who were
never actually friends and therefore never receive push notifications.

LINE's get_profile() raises a 404 LineBotApiError for any user_id that
isn't currently a friend (or has blocked the OA), so we use it as a proxy
friendship check. Does not modify any data.

Run: APP_ENV=production uv run python scripts/check_line_friendship.py
"""
import time

from linebot import LineBotApi
from linebot.exceptions import LineBotApiError
from sqlalchemy import select

from form_app.config import settings
from form_app.database import get_session_factory
from form_app.extensions import line_bot_helper
from form_app.models import Line_Info, Member

SessionFactory = get_session_factory(settings.DB)
line_bot_api = LineBotApi(line_bot_helper.configuration.access_token)

with SessionFactory() as session:
    line_infos = session.scalars(select(Line_Info)).all()
    print(f"Checking {len(line_infos)} bound LINE accounts...\n")

    not_friends = []
    errors = []

    for li in line_infos:
        try:
            line_bot_api.get_profile(li.user_id)
        except LineBotApiError as e:
            if e.status_code == 404:
                not_friends.append(li)
            else:
                errors.append((li, e))
        # avoid hammering the API
        time.sleep(0.05)

    print(f"Not friends (or blocked): {len(not_friends)}")
    for li in not_friends:
        member = session.query(Member).filter_by(phone_number=li.phone_number).first()
        name = member.name if member else "(no member record)"
        print(f"  phone={li.phone_number} name={name} line_user_id={li.user_id}")

    if errors:
        print(f"\nOther errors: {len(errors)}")
        for li, e in errors:
            print(f"  phone={li.phone_number} line_user_id={li.user_id} -> {e.status_code} {e}")

    print(f"\nDone. {len(line_infos) - len(not_friends) - len(errors)} confirmed friends.")
