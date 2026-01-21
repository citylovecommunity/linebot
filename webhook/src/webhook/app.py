import os
import re

from flask import Flask, abort, g, request
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

from shared.database.models import Line_Info
from shared.database.session_maker import get_session_factory

# 1. Import your existing database setup and models here
# Example: from models import db_session, UserInput
# For this example, I will assume a variable 'session' exists

app = Flask(__name__)

# 2. Configuration (Best stored in environment variables)
CHANNEL_ACCESS_TOKEN = os.getenv(
    'LINE_CHANNEL_ACCESS_TOKEN', 'YOUR_ACCESS_TOKEN')
CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET', 'YOUR_CHANNEL_SECRET')
DB = os.getenv('DB')


line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)


def get_db():
    """
    Opens a new session if one doesn't exist for this request.
    Stores it in 'g' so it can be accessed anywhere.
    """
    if 'db' not in g:
        # Create the session factory using your existing function
        Session = get_session_factory(DB)
        g.db = Session()
    return g.db


@app.teardown_appcontext
def close_db(error):
    """
    Closes the session automatically at the end of the request.
    This is CRITICAL to prevent connection pool exhaustion.
    """
    db = g.pop('db', None)
    if db is not None:
        db.close()


@app.route("/callback", methods=['POST'])
def callback():
    """
    Main webhook endpoint that LINE sends requests to.
    """
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("Invalid signature. Please check your channel access token/secret.")
        abort(400)

    return 'OK'


@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    msg = event.message.text.strip()
    line_user_id = event.source.user_id

    # Get the DB session
    session = get_db()

    # 1. Regex Match
    pattern = r"^綁定\s*(09\d{8})$"
    match = re.match(pattern, msg)

    if match:
        target_phone = match.group(1)

        # --- Step 1: Check if YOU (the Line User) are already bound ---
        # We assume your model is named 'Line_Info'
        existing_user_record = session.query(Line_Info).filter_by(
            line_user_id=line_user_id).first()

        if existing_user_record:
            # STRICT RULE: Existing users cannot change numbers
            reply_text = "❌ 您已經綁定過手機，如要更改請洽服務人員。"

        else:
            # --- Step 2: Check if the PHONE is already used by someone else ---
            phone_taken = session.query(Line_Info).filter_by(
                phone_number=target_phone).first()

            if phone_taken:
                reply_text = f"❌ 手機號碼 {target_phone} 已經被其他帳號綁定了。"
            else:
                # --- Step 3: Success Case - Create New Record ---
                new_info = Line_Info(
                    line_user_id=line_user_id,
                    phone_number=target_phone
                )
                session.add(new_info)

                try:
                    session.commit()
                    reply_text = f"✅ 綁定成功！\n您的號碼：{target_phone}"
                except Exception as e:
                    session.rollback()
                    app.logger.error(f"Database Error: {e}")
                    reply_text = "系統發生錯誤，請稍後再試。"

        # Send Reply
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=reply_text)
        )


if __name__ == "__main__":
    app.run(port=5000, debug=True)
