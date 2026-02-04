from flask import Blueprint, abort, current_app, request
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (ApiClient, MessagingApi, ReplyMessageRequest,
                                  TextMessage)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

from form_app.database import get_db
from form_app.extensions import line_bot_helper
from shared.database.models import Line_Info, Member

bp = Blueprint('webhook_bp', __name__)


@bp.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)
    current_app.logger.info("Request body: " + body)

    # handle webhook body
    try:
        line_bot_helper.handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'


@line_bot_helper.handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    # 1. Strip whitespace to prevent regex failure on hidden spaces
    text = event.message.text.strip()

    bp.logger.info(
        f"Received text: '{text}' from user: {event.source.user_id}")

    # 2. Capture the match object variable
    match = check_bind_match(text)

    # 3. Check if match exists (is not None)
    if match:
        bp.logger.info("Regex Matched! Processing binding...")

        # 4. Pass the MATCH object, not the text string
        reply_msg = run_binding(match, event.source.user_id)

        with ApiClient(line_bot_helper.configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[
                        TextMessage(text=reply_msg),
                    ]
                )
            )
    else:
        bp.logger.info("Regex did NOT match.")


def check_bind_match(msg):
    import re
    pattern = r"^綁定\s*(09\d{8})$"
    match = re.match(pattern, msg)
    return match


def run_binding(match, line_user_id):

    session = get_db()
    target_phone = match.group(1)

    # --- Step 1: Check if YOU (the Line User) are already bound ---
    # We assume your model is named 'Line_Info'
    existing_user_record = session.query(Line_Info).filter_by(
        user_id=line_user_id).first()

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
                user_id=line_user_id,
                phone_number=target_phone
            )
            session.add(new_info)

            try:
                session.commit()
                reply_text = f"✅ 綁定成功！\n您的號碼：{target_phone}"
            except Exception as e:
                session.rollback()
                current_app.logger.error(f"Database Error: {e}")
                reply_text = "系統發生錯誤，請稍後再試。"
    return reply_text
