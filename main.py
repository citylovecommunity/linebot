import json
import os
import re
import sys

import psycopg
from itsdangerous import URLSafeTimedSerializer
from fastapi import FastAPI, Request
from linebot.v3.messaging import (AsyncApiClient, AsyncMessagingApi,
                                  Configuration, ReplyMessageRequest,
                                  TextMessage)

# get channel_secret and channel_access_token from your environment variable
channel_secret = os.getenv('LINE_CHANNEL_SECRET', None)
channel_access_token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN', None)

TEST_USER_ID = os.getenv('TEST_USER_ID')

_APP_ENV = os.getenv('APP_ENV', 'development')
_APP_URL = (os.getenv('PROD_FORM_WEB_URL', '') if _APP_ENV == 'production'
            else os.getenv('DEV_FORM_WEB_URL', 'http://localhost:5678'))

_PREF_SALT = "member-pref"
_PREF_MAX_AGE = 2 * 3600  # 2 hours


def _make_pref_token(member_id: int) -> str:
    s = URLSafeTimedSerializer(os.getenv('SECRET_KEY', ''))
    return s.dumps(member_id, salt=_PREF_SALT)

if channel_secret is None:
    print('Specify LINE_CHANNEL_SECRET as environment variable.')
    sys.exit(1)
if channel_access_token is None:
    print('Specify LINE_CHANNEL_ACCESS_TOKEN as environment variable.')
    sys.exit(1)

configuration = Configuration(
    access_token=channel_access_token
)

app = FastAPI()
async_api_client = AsyncApiClient(configuration)
line_bot_api = AsyncMessagingApi(async_api_client)
parser = WebhookParser(channel_secret)

pattern = r"綁定\s*(09\d{8})"


@app.post("/")
async def handle_callback(request: Request):
    body = await request.body()
    body = body.decode()

    webhook_body = json.loads(body)
    for event in webhook_body['events']:
        event_type = event.get("type")

        if event_type == "message":
            message = event.get("message", {})
            if message.get("type") == "text":
                text = message.get("text", "").strip()
                if re.search(pattern, text):
                    await binding_phone_to_line(event)
                elif text == "綁定電話":
                    await handle_bind_menu(event)
                elif text == "修改偏好":
                    await handle_preferences_menu(event)
                elif text == "個人主頁":
                    await handle_homepage_menu(event)

        elif event_type == "postback":
            await handle_postback(event)
    return 'OK'


def _lookup_member_by_line_id(line_user_id: str):
    """Returns (member_id, phone_number, intro_url) or None if not bound."""
    with psycopg.connect(os.getenv('DB')) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT m.id, m.phone_number, m.user_info->>'會員介紹頁網址'
                FROM member m
                JOIN line_info li ON m.phone_number = li.phone_number
                WHERE li.user_id = %s
                """,
                (line_user_id,)
            )
            return cur.fetchone()


async def handle_bind_menu(event):
    line_user_id = event["source"]["userId"]
    reply_token = event["replyToken"]

    row = _lookup_member_by_line_id(line_user_id)
    if row:
        phone = row[1]
        masked = phone[:4] + "****" + phone[8:]
        reply_text = f"您已綁定手機號碼 {masked}。\n如需更換號碼，請聯絡客服。"
    else:
        reply_text = (
            "📱 請輸入以下格式來綁定您的手機號碼：\n\n"
            "綁定 09XXXXXXXX\n\n"
            "請將 09XXXXXXXX 替換為您的手機號碼。"
        )

    await line_bot_api.reply_message(
        ReplyMessageRequest(
            reply_token=reply_token,
            messages=[TextMessage(text=reply_text)]
        )
    )


async def handle_preferences_menu(event):
    line_user_id = event["source"]["userId"]
    reply_token = event["replyToken"]

    row = _lookup_member_by_line_id(line_user_id)
    if not row:
        reply_text = "請先綁定手機號碼，再使用此功能。\n\n點選選單中的「綁定電話」以了解如何綁定。"
    else:
        member_id = row[0]
        token = _make_pref_token(member_id)
        pref_url = f"{_APP_URL}/dashboard/preferences/{token}"
        reply_text = f"點此修改您的配對偏好（連結 2 小時內有效）：\n{pref_url}"

    await line_bot_api.reply_message(
        ReplyMessageRequest(
            reply_token=reply_token,
            messages=[TextMessage(text=reply_text)]
        )
    )


async def handle_homepage_menu(event):
    line_user_id = event["source"]["userId"]
    reply_token = event["replyToken"]

    row = _lookup_member_by_line_id(line_user_id)
    if not row:
        reply_text = "請先綁定手機號碼，再使用此功能。"
    else:
        intro_url = row[2]
        if intro_url:
            reply_text = f"您的個人介紹頁：\n{intro_url}"
        else:
            reply_text = "您的個人介紹頁尚未設定，請聯絡客服協助建立。"

    await line_bot_api.reply_message(
        ReplyMessageRequest(
            reply_token=reply_token,
            messages=[TextMessage(text=reply_text)]
        )
    )


async def handle_postback(event):
    data = event["postback"]["data"]
    user_id = event["source"]["userId"]
    reply_token = event["replyToken"]

    if data == "action=arrived":
        await handle_arrived(user_id, reply_token)


async def handle_arrived(user_id, reply_token):
    # ① 回覆按按鈕的使用者（一定要先）
    await line_bot_api.reply_message(
        ReplyMessageRequest(
            reply_token=reply_token,
            messages=[TextMessage(text="已通知對方，請稍候 🙌")]
        )
    )

    # # ② 查詢約會資訊
    # date_id = get_current_date_id(user_id)
    # other_user_id = get_other_user(date_id, user_id)

    # # ③ 更新狀態（建議在 push 前）
    # mark_user_arrived(date_id, user_id)

#     push_seen_question(TEST_USER_ID)


# def push_seen_question(other_user_id):
#     message = TextSendMessage(
#         text="對方已抵達，你是否已看到對方？",
#         quick_reply=QuickReply(
#             items=[
#                 QuickReplyButton(
#                     action=PostbackAction(
#                         label="👀 我看到對方了",
#                         data=f"action=seen"
#                     )
#                 ),
#                 QuickReplyButton(
#                     action=PostbackAction(
#                         label="❓ 還沒看到",
#                         data=f"action=not_seen"
#                     )
#                 )
#             ]
#         )
#     )

#     line_bot_api.push_message(other_user_id, message)


async def debug_event_record(body):
    event_json = json.dumps(body)
    with psycopg.connect(os.getenv('DB')) as conn:
        with conn.cursor() as cur:
            stmt = """
                insert into events (event)
                values (%s)
            """
            cur.execute(stmt, (event_json,))
        conn.commit()


async def binding_phone_to_line(event):
    phone_number = re.search(pattern, event['message']['text']).group(1)
    with psycopg.connect(os.getenv('DB')) as conn:
        with conn.cursor() as cur:
            stmt = """
                        insert into line_info (phone_number, user_id)
                        values (%(phone_number)s, %(user_id)s)
                        on conflict (user_id) do nothing
                        returning user_id
                        """
            result = cur.execute(
                stmt, {'phone_number': phone_number, 'user_id': event['source']['userId']})
            result = cur.fetchone()
            if result:
                reply = '綁定成功🎉'
            else:
                reply = '已綁定過，若要更換號碼，請聯絡客服'
        conn.commit()

    await line_bot_api.reply_message(
        ReplyMessageRequest(
            reply_token=event["replyToken"],
            messages=[TextMessage(text=reply)]
        )
    )
