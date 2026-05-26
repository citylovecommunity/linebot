from collections import defaultdict
from datetime import datetime, timezone, timedelta

from linebot import LineBotApi
from linebot.models import TextMessage
from sqlalchemy import and_
from sqlalchemy.orm import joinedload

from form_app.config import settings
from form_app.extensions import line_bot_helper
from form_app.models import (
    DateProposal, Matching, Member, Message,
    GroupMatching, GroupMessage, GroupDateProposal,
)

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
        .options(joinedload(Message.matching), joinedload(Message.user))
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
        session.query(DateProposal)
        .where(
            DateProposal.is_pending_notified.is_not(True),
            DateProposal.status == 'PENDING')
        .options(joinedload(DateProposal.matching))
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
        session.query(DateProposal)
        .where(
            DateProposal.is_confirmed_notified.is_not(True),
            DateProposal.status == 'CONFIRMED')
        .options(joinedload(DateProposal.matching))
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
        .options(joinedload(Matching.subject), joinedload(Matching.object))
        .all()
    )

    for matching in new_matchings:
        pairs = [
            (matching.subject, matching.object),
            (matching.object, matching.subject),
        ]
        for member, partner in pairs:
            if not member or not partner:
                continue
            from form_app.services.match_intro import generate_match_intro_long
            intro = generate_match_intro_long(member, partner, matching.cool_name)
            text = (
                f"🎉 {member.proper_name}，{intro}\n"
                f"{APP_URL}/dashboard/{matching.id}"
            )
            updates[member.id].append(text)
        matching.is_match_notified = True

    return updates


def collect_new_group_match_texts(session):
    updates = defaultdict(list)
    new_groups = (
        session.query(GroupMatching)
        .filter(GroupMatching.is_notified.is_(False))
        .all()
    )
    for group in new_groups:
        partner_names = ', '.join(m.proper_name for m in group.members)
        for member in group.members:
            others = [m.proper_name for m in group.members if m.id != member.id]
            text = (
                f"🎉 您有一個新的群組配對！\n\n"
                f"代號：{group.cool_name}\n"
                f"成員：{'、'.join(others)}\n\n"
                f"👇 進入群組對話：\n{APP_URL}/dashboard/group/{group.id}"
            )
            updates[member.id].append(text)
        group.is_notified = True
    return updates


def collect_group_message_texts(session):
    updates = defaultdict(list)
    unnotified = (
        session.query(GroupMessage)
        .filter(GroupMessage.is_notified.is_not(True))
        .options(joinedload(GroupMessage.group), joinedload(GroupMessage.sender))
        .all()
    )
    by_group = defaultdict(list)
    for msg in unnotified:
        by_group[msg.group_id].append(msg)

    for group_id, msgs in by_group.items():
        group = msgs[0].group
        sender_ids = {m.sender_id for m in msgs}
        for member in group.members:
            if member.id in sender_ids:
                continue
            count = len(msgs)
            if count <= 3:
                lines = "\n".join(
                    f"  {m.sender.proper_name}: {_trim(m.content)}" for m in msgs
                )
                text = (
                    f"📩 群組 {group.cool_name} — {count} 則未讀\n"
                    f"{lines}\n\n"
                    f"🔗 馬上回覆: {APP_URL}/dashboard/group/{group_id}"
                )
            else:
                text = (
                    f"📩 群組 {group.cool_name} — 您有 {count} 則未讀訊息\n\n"
                    f"🔗 馬上回覆: {APP_URL}/dashboard/group/{group_id}"
                )
            updates[member.id].append(text)
        for msg in msgs:
            msg.is_notified = True
    return updates


def collect_group_proposal_texts(session):
    updates = defaultdict(list)
    proposals = (
        session.query(GroupDateProposal)
        .filter(
            GroupDateProposal.is_notified.is_not(True),
            GroupDateProposal.is_deleted.is_(False),
        )
        .options(joinedload(GroupDateProposal.group), joinedload(GroupDateProposal.proposer))
        .all()
    )
    for proposal in proposals:
        group = proposal.group
        date_str = proposal.proposed_datetime.strftime('%m/%d %H:%M')
        text = (
            f"📅 群組 {group.cool_name}\n\n"
            f"{proposal.proposer.proper_name} 提議在 {date_str} 前往「{proposal.restaurant_name}」！\n\n"
            f"🔗 查看詳情: {APP_URL}/dashboard/group/{group.id}"
        )
        for member in group.members:
            updates[member.id].append(text)
        proposal.is_notified = True
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

    group_match_updates = collect_new_group_match_texts(session)
    for uid, texts in group_match_updates.items():
        all_notifications[uid].extend(texts)

    group_msg_updates = collect_group_message_texts(session)
    for uid, texts in group_msg_updates.items():
        all_notifications[uid].extend(texts)

    group_proposal_updates = collect_group_proposal_texts(session)
    for uid, texts in group_proposal_updates.items():
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
