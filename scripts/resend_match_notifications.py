"""
Resets is_match_notified for the 47 matchings created at 2026-03-21 18:29
and re-sends new-match LINE notifications with correct matching IDs.

Run: APP_ENV=production uv run python scripts/resend_match_notifications.py
"""
from collections import defaultdict
from datetime import datetime, timezone

from linebot import LineBotApi
from linebot.models import TextMessage
from sqlalchemy import select

from form_app.config import settings
from form_app.database import get_session_factory
from form_app.extensions import line_bot_helper
from form_app.models import Matching, MatchingStatus

TARGET_IDS = [
    1409, 1410, 1411, 1412, 1413, 1414, 1415, 1416, 1417, 1418,
    1419, 1420, 1421, 1423, 1424, 1425, 1426, 1431, 1432, 1434,
    1436, 1437, 1438, 1439, 1440, 1441, 1442, 1443, 1444, 1445,
    1446, 1447, 1448, 1449, 1451, 1452, 1453, 1454, 1455, 1456,
    1457, 1458, 1459, 1460, 1461, 1463, 1464,
]

APP_URL = settings.APP_URL

SessionFactory = get_session_factory(settings.DB)

with SessionFactory() as session:
    matchings = session.scalars(
        select(Matching).where(Matching.id.in_(TARGET_IDS))
    ).all()

    print(f"Loaded {len(matchings)} matchings from DB.")

    # Step 1: Reset is_match_notified so collect logic picks them up
    for m in matchings:
        m.is_match_notified = False
    session.flush()

    # Step 2: Build notifications
    all_notifications = defaultdict(list)  # { member_id: [text, ...] }

    for matching in matchings:
        for member in (matching.subject, matching.object):
            if not member:
                continue
            text = (
                f"🎉 恭喜！你有一個新的配對！\n\n"
                f"你的新夥伴正在等你 👀\n"
                f"代號：{matching.cool_name}\n\n"
                f"👇 登入查看：\n{APP_URL}/dashboard/{matching.id}"
            )
            all_notifications[member.id].append(text)
        matching.is_match_notified = True

    print(f"Prepared notifications for {len(all_notifications)} members.\n")

    # Step 3: Send via LINE
    line_bot_api = LineBotApi(line_bot_helper.configuration.access_token)
    now = datetime.now(timezone.utc)

    sent = 0
    skipped = 0
    for user_id_db, messages in all_notifications.items():
        member = session.get(type(matchings[0].subject), user_id_db)
        if not member or not member.line_info:
            print(f"  SKIP user #{user_id_db} — no LINE info")
            skipped += 1
            continue

        target_line_id = member.line_info.user_id
        line_messages = [TextMessage(text=m) for m in messages]

        print(f"  Sending to {member.name} (#{user_id_db}) → LINE {target_line_id}")
        line_bot_api.push_message(target_line_id, messages=line_messages)
        member.last_notification_sent_at = now
        sent += 1

    session.commit()
    print(f"\nDone. Sent: {sent}, Skipped (no LINE): {skipped}")
