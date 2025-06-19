
import os
import sys

from fastapi import FastAPI, HTTPException, Request
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (AsyncApiClient, AsyncMessagingApi,
                                  Configuration, ReplyMessageRequest,
                                  TextMessage)
from linebot.v3.webhook import WebhookParser
from linebot.v3.webhooks import MessageEvent, TextMessageContent
import psycopg2
import re

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
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = await request.body()
    body = body.decode()

    try:
        events = parser.parse(body, signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    for event in events:
        if not isinstance(event, MessageEvent):
            continue
        if not isinstance(event.message, TextMessageContent):
            continue

        if re.search(pattern, event.message):
            binding_phone_to_line(event)

    return 'OK'


async def binding_phone_to_line(event):
    phone_number = re.search(pattern, event.message).group(1)
    with psycopg2.connect(os.getenv('DB')) as conn:
        with conn.cursor() as cur:
            # 先檢查有無在db，若有發送已經綁定

            # 若無，insert進db並發送註冊成功訊息
            # TODO: 把db建出來
            stmt = """
                        insert into (phone_number, user_id)
                        values %(phone_number)s, %(user_id)s
                        on conflict (phone_number) do nothing
                        returning phone_number          
                        """
            result = cur.execute(
                stmt, {'phone': phone_number, 'user_id': event.source.userId})
            if result:
                reply = '綁定成功🎉'
            else:
                reply = '已綁定過，若要更換電話，請聯絡客服'

    await line_bot_api.reply_message(
        ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TextMessage(text=reply)]
        )
    )
