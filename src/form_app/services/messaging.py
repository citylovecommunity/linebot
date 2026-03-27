from collections import defaultdict
from datetime import datetime, timezone, timedelta

from linebot import LineBotApi
from linebot.models import TextMessage
from sqlalchemy import and_
from sqlalchemy.orm import joinedload

from form_app.config import settings
from form_app.extensions import line_bot_helper
from form_app.models import DateProposal, Matching, Member, Message

APP_URL = settings.APP_URL


_MAX_CONTENT_LEN = 50
_SILENCE_WINDOW_SECONDS = 10 * 60  # 10 minutes


def _trim(text: str) -> str:
    return text if len(text) <= _MAX_CONTENT_LEN else text[:_MAX_CONTENT_LEN] + '...'


def collect_unread_message_texts(session):
    """
    Returns a dict: { user_id: [text, ...] }
    Messages are bundled per conversation (one LINE message per matching).
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

    # Group by (receiver_id, matching_id)
    by_convo = defaultdict(list)
    for msg in un_notified_messages:
        by_convo[(msg.receiver_id, msg.matching_id)].append(msg)

    for (receiver_id, matching_id), msgs in by_convo.items():
        matching = msgs[0].matching
        count = len(msgs)

        if count <= 3:
            lines = "\n".join(
                f"  {m.user.proper_name}: {_trim(m.content)}" for m in msgs
            )
            text = (
                f"📩 {matching.cool_name} — {count} 則未讀\n"
                f"{lines}\n\n"
                f"🔗 馬上回覆: {APP_URL}/dashboard/{matching_id}"
            )
        else:
            text = (
                f"📩 {matching.cool_name} — 您有 {count} 則未讀訊息\n\n"
                f"🔗 馬上回覆: {APP_URL}/dashboard/{matching_id}"
            )

        updates[receiver_id].append(text)
        for msg in msgs:
            msg.is_notified = True

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


def collect_new_match_texts(session):
    """
    Returns a dict: { user_id: ["Text 1"] }
    Fires once per new matching for both members.
    """
    updates = defaultdict(list)

    new_matchings = (
        session.query(Matching)
        .filter(Matching.is_match_notified.is_not(True))
        .all()
    )

    for matching in new_matchings:
        for member in (matching.subject, matching.object):
            if not member:
                continue
            text = (
                f"🎉 恭喜！你有一個新的配對！\n\n"
                f"你的新夥伴正在等你 👀\n"
                f"代號：{matching.cool_name}\n\n"
                f"👇 登入查看：\n{APP_URL}/dashboard/{matching.id}"
            )
            updates[member.id].append(text)
        matching.is_match_notified = True

    return updates


def process_all_notifications(session):
    # 1. Initialize Aggregator
    # This will hold all messages for all users: { user_id: [msg1, msg2] }
    dev = settings.is_dev

    all_notifications = defaultdict(list)

    # 2. Run Collectors
    match_updates = collect_new_match_texts(session)
    for uid, texts in match_updates.items():
        all_notifications[uid].extend(texts)

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

    # Commit all is_*_notified flags before pushing so they are persisted
    # even if a LINE API call fails later.
    session.commit()

    line_bot_api = LineBotApi(line_bot_helper.configuration.access_token)

    now = datetime.now(timezone.utc)

    # 4. Eager-load all members with line_info in one query to avoid lazy-loads
    # after the commit (which expires all ORM objects).
    user_ids = list(all_notifications.keys())
    members = (
        session.query(Member)
        .filter(Member.id.in_(user_ids))
        .options(joinedload(Member.line_info))
        .all()
    )
    members_by_id = {m.id: m for m in members}

    for user_id_db, messages in all_notifications.items():

        user = members_by_id.get(user_id_db)
        if not user:
            continue

        # Silence window: skip if user was active on the dashboard recently
        if user.last_seen_at and (now - user.last_seen_at).total_seconds() < _SILENCE_WINDOW_SECONDS:
            continue

        if dev:
            target_line_id = settings.LINE_TEST_USER_ID
        else:
            if not user.line_info:
                continue
            target_line_id = user.line_info.user_id

        # LINE allows max 5 messages per push; bundle overflow into a summary
        if len(messages) <= 5:
            line_messages = [TextMessage(text=m) for m in messages]
        else:
            line_messages = [TextMessage(text=m) for m in messages[:4]]
            line_messages.append(TextMessage(text=f"⋯ 還有 {len(messages) - 4} 則通知，請登入查看。"))

        print(f"Sending {len(line_messages)} msgs to user {user.id}")

        try:
            line_bot_api.push_message(target_line_id, messages=line_messages)
            user.last_notification_sent_at = now
        except Exception as e:
            print(f"Failed to push LINE message to user {user.id}: {e}")
