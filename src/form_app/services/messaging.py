from collections import defaultdict
from datetime import datetime, timezone

from linebot import LineBotApi
from linebot.models import TextMessage
from sqlalchemy import and_

from form_app.config import settings
from form_app.extensions import line_bot_helper
from form_app.models import DateProposal, Member, Message

APP_URL = settings.APP_URL


def collect_unread_message_texts(session):
    """
    Returns a dict: { user_id: ["Text 1"] }
    """
    updates = defaultdict(list)

    un_notified_messages = (
        session.query(Message)
        .filter(
            and_(Message.read_at.is_(None),
                 Message.is_notified.is_not(True)),
        )
        .all()
    )
    for message in un_notified_messages:
        matching = message.matching
        text = f"""📩 {matching.cool_name} {message.user.proper_name}: {message.content}\n🔗 馬上回覆: {APP_URL}/dashboard/{matching.id}
        """
        updates[message.receiver_id].append(text)
        message.is_notified = True

    return updates

# Collector 2: Date Proposals (New Feature)


def collect_date_proposal_texts(session):
    """
    Returns a dict: { user_id: ["Text 1", "Text 2"] }
    """
    updates = defaultdict(list)

    # Query: Find PENDING proposals that haven't been notified yet
    # Assuming you have a 'notified' flag or checking timestamps on proposals
    proposals = (
        session.query(DateProposal).where(
            DateProposal.is_pending_notified.is_not(True),
            DateProposal.status == 'PENDING')
    )

    for proposal in proposals:
        # --- CUSTOM TEXT LOGIC ---
        # Formatting the date nicely
        date_str = proposal.proposed_datetime.strftime('%m/%d %H:%M')
        matching = proposal.matching
        text = f"""📅 {matching.cool_name}\n\n您的夥伴邀請您在 {date_str} 前往「{proposal.restaurant_name}」出任務！\n\n👇 快點擊確認吧！ {APP_URL}/dashboard/{matching.id}
        """

        updates[proposal.proposer_id].append(text)
        updates[matching.get_partner(proposal.proposer_id).id].append(text)

        # Mark as processed in this specific scope so we don't fetch it next time
        proposal.is_pending_notified = True

    return updates


def collect_confirmed_date_proposal_texts(session):
    """
    Returns a dict: { user_id: ["Text 1", "Text 2"] }
    """
    updates = defaultdict(list)

    # Query: Find PENDING proposals that haven't been notified yet
    # Assuming you have a 'notified' flag or checking timestamps on proposals
    proposals = (
        session.query(DateProposal).where(
            DateProposal.is_confirmed_notified.is_not(True),
            DateProposal.status == 'CONFIRMED')
    )

    for proposal in proposals:
        # --- CUSTOM TEXT LOGIC ---
        # Formatting the date nicely
        date_str = proposal.proposed_datetime.strftime('%m/%d %H:%M')
        matching = proposal.matching
        text = f"""✅ 任務確認！\n\n與 {matching.cool_name} 的夥伴在 （{date_str}） {proposal.restaurant_name} 的任務已被確認！\n\n🔗 查看行程詳情： {APP_URL}/dashboard/{matching.id}
        """

        updates[proposal.proposer_id].append(text)
        updates[matching.get_partner(proposal.proposer_id).id].append(text)

        # Mark as processed in this specific scope so we don't fetch it next time
        proposal.is_confirmed_notified = True

    return updates


def process_all_notifications(session):
    # 1. Initialize Aggregator
    # This will hold all messages for all users: { user_id: [msg1, msg2] }
    dev = settings.is_dev

    all_notifications = defaultdict(list)

    # 2. Run Collectors
    # Merge results from messages
    msg_updates = collect_unread_message_texts(session)
    for uid, texts in msg_updates.items():
        all_notifications[uid].extend(texts)

    # Merge results from date proposals
    date_updates = collect_date_proposal_texts(session)
    for uid, texts in date_updates.items():
        all_notifications[uid].extend(texts)

    date_confirmed_updates = collect_confirmed_date_proposal_texts(session)
    for uid, texts in date_confirmed_updates.items():
        all_notifications[uid].extend(texts)

    # If nothing to do, exit
    if not all_notifications:
        return

    line_bot_api = LineBotApi(line_bot_helper.configuration.access_token)

    # 4. Iterate over distinct Users
    for user_id_db, messages in all_notifications.items():

        # Fetch User Object to check silence window & get Line ID
        user = session.get(Member, user_id_db)

        if dev:
            target_line_id = settings.LINE_TEST_USER_ID
        else:
            target_line_id = user.line_info.user_id

        line_messages = [TextMessage(text=m) for m in messages[:5]]

        print(
            f"Sending {len(messages)} msgs to Test User for ID {user.id}")

        line_bot_api.push_message(
            target_line_id,
            messages=line_messages
        )

        # Update Timestamp
        user.last_notification_sent_at = datetime.now(timezone.utc)
