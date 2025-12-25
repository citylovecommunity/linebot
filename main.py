import json
import os
import re
import sys

import psycopg
from fastapi import FastAPI, HTTPException, Request
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (AsyncApiClient, AsyncMessagingApi,
                                  Configuration, ReplyMessageRequest,
                                  TextMessage)
from linebot.v3.webhook import WebhookParser
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from linebot.models import TextSendMessage


# get channel_secret and channel_access_token from your environment variable
channel_secret = os.getenv('LINE_CHANNEL_SECRET', None)
channel_access_token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN', None)

TEST_USER_ID = os.getenv('TEST_USER_ID')

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
    # signature = request.headers['X-Line-Signature']

    # get request body as text
    body = await request.body()
    body = body.decode()

    # try:
    #     events = parser.parse(body, signature)
    # except InvalidSignatureError:
    #     raise HTTPException(status_code=400, detail="Invalid signature")

    webhook_body = json.loads(body)
#    await debug_event_record(body)
    for event in webhook_body['events']:
        event_type = event.get("type")

        # 1️⃣ 文字訊息（例如你原本的綁電話邏輯）
        if event_type == "message":
            message = event.get("message", {})
            if message.get("type") == "text":
                text = message.get("text", "")
                if re.search(pattern, text):
                    await binding_phone_to_line(event)

        # 2️⃣ Postback（我已抵達 / 看到 / 沒看到）
        elif event_type == "postback":
            await handle_postback(event)
    return 'OK'


def handle_postback(event):
    data = event["postback"]["data"]
    user_id = event["source"]["userId"]
    reply_token = event["replyToken"]

    if data == "action=arrived":
        handle_arrived(user_id, reply_token)


def handle_arrived(user_id, reply_token):
    # ① 回覆按按鈕的使用者（一定要先）
    line_bot_api.reply_message(
        reply_token,
        TextSendMessage(text="已通知對方，請稍候 🙌")
    )

    # # ② 查詢約會資訊
    # date_id = get_current_date_id(user_id)
    # other_user_id = get_other_user(date_id, user_id)

    # # ③ 更新狀態（建議在 push 前）
    # mark_user_arrived(date_id, user_id)

    # ④ 用 push 通知另一方
    line_bot_api.push_message(
        TEST_USER_ID,
        TextSendMessage(
            text="對方已抵達，你是否已看到對方？"
        )
    )


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
