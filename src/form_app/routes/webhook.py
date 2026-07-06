import json as _json
import urllib.request

from flask import Blueprint, abort, current_app, request
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (ApiClient, MessagingApi, ReplyMessageRequest,
                                  TextMessage)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

from form_app.config import settings
from form_app.database import get_db
from form_app.extensions import line_bot_helper
from form_app.models import LeadSubmission, LeadSubmissionStatus, Line_Info, Member

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

    current_app.logger.info(
        f"Received text: '{text}' from user: {event.source.user_id}")

    # 2. Capture the match object variable
    match = check_bind_match(text)

    # 3. Check if match exists (is not None)
    if match:
        current_app.logger.info("Regex Matched! Processing binding...")

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
        current_app.logger.info("Regex did NOT match.")


def check_bind_match(msg):
    import re
    pattern = r"^綁定\s*(09\d{8})$"
    match = re.match(pattern, msg)
    return match


@bp.route("/webhook/meta-lead", methods=["GET"])
def meta_lead_verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token and token == settings.META_VERIFY_TOKEN:
        return challenge, 200
    return "Forbidden", 403


@bp.route("/webhook/meta-lead", methods=["POST"])
def meta_lead_webhook():
    data = request.json or {}
    if data.get("object") != "page":
        return "OK", 200
    for entry in data.get("entry", []):
        for change in entry.get("changes", []):
            if change.get("field") != "leadgen":
                continue
            lead_id = change.get("value", {}).get("leadgen_id")
            if lead_id:
                try:
                    _save_lead(lead_id)
                except Exception as e:
                    current_app.logger.error(f"Error processing lead {lead_id}: {e}")
    return "OK", 200


def _save_lead(lead_id: str):
    from datetime import datetime as _dt
    session = get_db()

    if session.query(LeadSubmission).filter_by(meta_lead_id=lead_id).first():
        return

    if not settings.META_PAGE_ACCESS_TOKEN:
        current_app.logger.warning("META_PAGE_ACCESS_TOKEN not set")
        return

    url = f"https://graph.facebook.com/v20.0/{lead_id}?access_token={settings.META_PAGE_ACCESS_TOKEN}"
    with urllib.request.urlopen(url, timeout=10) as resp:
        lead_data = _json.loads(resp.read())

    fields = {}
    for f in lead_data.get("field_data", []):
        vals = f.get("values", [])
        fields[f["name"]] = vals[0] if vals else ""

    name = fields.get("full_name") or fields.get("name", "")
    phone = (fields.get("phone_number") or fields.get("phone", "")).replace(" ", "")

    gender = ""
    age = None
    line_id = ""
    for key, val in fields.items():
        lk = key.lower()
        if "性別" in key or lk == "gender":
            gender = "F" if "女" in val else ("M" if "男" in val else "")
        elif "年齡" in key or lk == "age":
            try:
                age = int(val)
            except (ValueError, TypeError):
                pass
        elif "line" in lk:
            line_id = val

    try:
        submitted_at = _dt.fromisoformat(lead_data.get("created_time", "").replace("Z", "+00:00"))
    except Exception:
        submitted_at = _dt.now()

    lead = LeadSubmission(
        meta_lead_id=lead_id,
        name=name or None,
        phone_number=phone or None,
        gender=gender or None,
        age=age,
        line_id=line_id or None,
        raw_data=fields,
        submitted_at=submitted_at,
    )
    session.add(lead)
    session.commit()
    current_app.logger.info(f"Saved Meta lead {lead_id}: {name}")


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
