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

# get channel_secret and channel_access_token from your environment variable
channel_secret = os.getenv('LINE_CHANNEL_SECRET', None)
channel_access_token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN', None)
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
        if re.search(pattern, event['message']['text']):
            await binding_phone_to_line(event)

    return 'OK'


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
                        values %(phone_number)s, %(user_id)s
                        on conflict (user_id) do nothing
                        returning user_id
                        """
            result = cur.execute(
                stmt, {'phone_number': phone_number, 'user_id': event['source']['userId']})
            if result:
                reply = '綁定成功🎉'
            else:
                reply = '已綁定過，若要更換號碼，請聯絡客服'
        conn.commit()

    await line_bot_api.reply_message(
        ReplyMessageRequest(
            reply_token=event["reply_token"],
            messages=[TextMessage(text=reply)]
        )
    )
