import logging
from collections import defaultdict, namedtuple
from datetime import datetime, timezone, timedelta

from linebot import LineBotApi
from linebot.exceptions import LineBotApiError
from linebot.models import TextMessage
from sqlalchemy import and_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import joinedload

from form_app.config import settings
from form_app.extensions import line_bot_helper
from form_app.models import (
    DateProposal, Matching, Member, Message, NotificationDelivery,
    GroupMatching, GroupMessage, GroupDateProposal,
)
from form_app.services.group_matching import PICKLE_BALL_CAMPAIGN
from form_app.services.scoring import has_pickle_ball_affinity

APP_URL = settings.APP_URL


_MAX_CONTENT_LEN = 50
_SILENCE_WINDOW_SECONDS = 10 * 60  # 10 minutes

# A queued notification for one recipient. `keys` lists the (event_type,
# event_id) pairs this text covers — once the push actually succeeds, a
# NotificationDelivery row is recorded for each key so a retry never
# re-notifies this recipient for the same event, even if a *different*
# recipient of the same broadcast event failed and needs a retry.
NotifItem = namedtuple("NotifItem", ["text", "keys"])


def _trim(text: str) -> str:
    return text if len(text) <= _MAX_CONTENT_LEN else text[:_MAX_CONTENT_LEN] + '...'


def _delivered_map(session, event_type: str, event_ids: list[int]) -> dict[int, set[int]]:
    """Returns { event_id: {member_id, ...} } of recipients already delivered for this event type."""
    if not event_ids:
        return {}
    rows = (
        session.query(NotificationDelivery.event_id, NotificationDelivery.member_id)
        .filter(
            NotificationDelivery.event_type == event_type,
            NotificationDelivery.event_id.in_(event_ids),
        )
        .all()
    )
    delivered = defaultdict(set)
    for event_id, member_id in rows:
        delivered[event_id].add(member_id)
    return delivered


def _record_delivery(session, member_id: int, items: list[NotifItem]):
    """Marks every event key covered by `items` as delivered to `member_id`."""
    keys = {key for item in items for key in item.keys}
    if not keys:
        return
    rows = [
        {"member_id": member_id, "event_type": event_type, "event_id": event_id}
        for event_type, event_id in keys
    ]
    stmt = pg_insert(NotificationDelivery).values(rows)
    stmt = stmt.on_conflict_do_nothing(
        index_elements=["member_id", "event_type", "event_id"]
    )
    session.execute(stmt)


def collect_unread_message_texts(session):
    """
    Returns a dict: { user_id: [NotifItem, ...] }
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
    if not un_notified_messages:
        return updates

    delivered = _delivered_map(session, 'message', [m.id for m in un_notified_messages])

    # Group by (receiver_id, matching_id)
    by_convo = defaultdict(list)
    for msg in un_notified_messages:
        receiver_id = msg.receiver_id
        if receiver_id in delivered.get(msg.id, set()):
            # Already delivered in a prior run whose flag-write never landed.
            msg.is_notified = True
            continue
        by_convo[(receiver_id, msg.matching_id)].append(msg)

    for (receiver_id, matching_id), msgs in by_convo.items():
        matching = msgs[0].matching
        count = len(msgs)

        if count <= 3:
            lines = "\n".join(
                f"  {m.user.proper_name}: {_trim(m.content)}" for m in msgs
            )
            text = (
                f"🔔 {matching.cool_name} — {count} 則未讀\n"
                f"{lines}\n\n"
                f"👇 點此開啟對話：\n{APP_URL}/dashboard/{matching_id}"
            )
        else:
            text = (
                f"🔔 {matching.cool_name} — 您有 {count} 則未讀訊息\n\n"
                f"👇 點此開啟對話：\n{APP_URL}/dashboard/{matching_id}"
            )

        updates[receiver_id].append(
            NotifItem(text, [('message', m.id) for m in msgs])
        )

    return updates

# Collector 2: Date Proposals (New Feature)


def collect_date_proposal_texts(session):
    """
    Returns a dict: { user_id: [NotifItem, ...] }
    """
    updates = defaultdict(list)

    proposals = (
        session.query(DateProposal)
        .where(
            DateProposal.is_pending_notified.is_not(True),
            DateProposal.status == 'PENDING')
        .options(joinedload(DateProposal.matching))
        .all()
    )
    if not proposals:
        return updates

    delivered = _delivered_map(session, 'date_pending', [p.id for p in proposals])

    for proposal in proposals:
        matching = proposal.matching
        partner = matching.get_partner(proposal.proposer_id)
        recipients = [proposal.proposer_id] + ([partner.id] if partner else [])
        already = delivered.get(proposal.id, set())

        if set(recipients) <= already:
            proposal.is_pending_notified = True
            continue

        date_str = proposal.proposed_datetime.strftime('%m/%d %H:%M')
        text = f"""📅 {matching.cool_name}\n\n您的夥伴邀請您在 {date_str} 前往「{proposal.restaurant_name}」出任務！\n\n👇 快點擊確認吧！ {APP_URL}/dashboard/{matching.id}
        """

        for uid in recipients:
            if uid in already:
                continue
            updates[uid].append(NotifItem(text, [('date_pending', proposal.id)]))

    return updates


def collect_confirmed_date_proposal_texts(session):
    """
    Returns a dict: { user_id: [NotifItem, ...] }
    """
    updates = defaultdict(list)

    proposals = (
        session.query(DateProposal)
        .where(
            DateProposal.is_confirmed_notified.is_not(True),
            DateProposal.status == 'CONFIRMED')
        .options(joinedload(DateProposal.matching))
        .all()
    )
    if not proposals:
        return updates

    delivered = _delivered_map(session, 'date_confirmed', [p.id for p in proposals])

    for proposal in proposals:
        matching = proposal.matching
        partner = matching.get_partner(proposal.proposer_id)
        recipients = [proposal.proposer_id] + ([partner.id] if partner else [])
        already = delivered.get(proposal.id, set())

        if set(recipients) <= already:
            proposal.is_confirmed_notified = True
            continue

        date_str = proposal.proposed_datetime.strftime('%m/%d %H:%M')
        text = f"""✅ 任務確認！\n\n與 {matching.cool_name} 的夥伴在 （{date_str}） {proposal.restaurant_name} 的任務已被確認！\n\n🔗 查看行程詳情： {APP_URL}/dashboard/{matching.id}
        """

        for uid in recipients:
            if uid in already:
                continue
            updates[uid].append(NotifItem(text, [('date_confirmed', proposal.id)]))

    return updates


def collect_new_match_texts(session):
    """
    Returns a dict: { user_id: [NotifItem, ...] }
    Fires once per new matching for both members.
    """
    updates = defaultdict(list)

    candidates = (
        session.query(Matching)
        .filter(Matching.is_match_notified.is_not(True))
        .options(
            joinedload(Matching.subject).selectinload(Member.tags),
            joinedload(Matching.object).selectinload(Member.tags),
        )
        .all()
    )
    if not candidates:
        return updates

    delivered = _delivered_map(session, 'match', [m.id for m in candidates])

    for matching in candidates:
        required = {matching.subject_id, matching.object_id}
        already = delivered.get(matching.id, set())

        if required <= already:
            matching.is_match_notified = True
            continue

        url = f"{APP_URL}/dashboard/{matching.id}"
        if (matching.subject and matching.object
                and has_pickle_ball_affinity(matching.subject)
                and has_pickle_ball_affinity(matching.object)):
            text = (
                f"Hi 本週你的新球友來了！\n"
                f"→ 點此查看 {url}\n"
                f"提醒：打球時間地點由大家自行約定，不限任何特定時間和地點"
            )
        else:
            text = (
                f"推薦你認識新朋友的時間來囉！\n\n"
                f"您們可以一起相約喝個咖啡，\n"
                f"或是本季我們主打大家一起認識現火熱的匹克球運動，\n"
                f"歡迎你們一起相約共襄盛舉！\n"
                f"詳見對話框的任務牆～\n\n"
                f"{url}"
            )

        for member, partner in (
            (matching.subject, matching.object),
            (matching.object, matching.subject),
        ):
            if not member or not partner or member.id in already:
                continue
            updates[member.id].append(NotifItem(text, [('match', matching.id)]))

    return updates


def collect_new_group_match_texts(session):
    updates = defaultdict(list)
    new_groups = (
        session.query(GroupMatching)
        .filter(GroupMatching.is_notified.is_(False))
        .all()
    )
    if not new_groups:
        return updates

    delivered = _delivered_map(session, 'group_match', [g.id for g in new_groups])

    for group in new_groups:
        members = group.members
        required = {m.id for m in members}
        already = delivered.get(group.id, set())

        if required <= already:
            group.is_notified = True
            continue

        is_pickleball = group.source_campaign == PICKLE_BALL_CAMPAIGN
        for member in members:
            if member.id in already:
                continue
            others = [m.proper_name for m in members if m.id != member.id]
            if is_pickleball:
                if group.host_member_id:
                    host_note = (
                        "🏓 本局由你主揪，打球時間地點由你決定唷！"
                        if group.host_member_id == member.id
                        else f"• 提醒：本局由 {group.host.proper_name} 主揪，打球時間地點由他決定"
                    )
                else:
                    host_note = "• 提醒：打球時間地點由大家自行約定，不限任何特定時間和地點"
                text = (
                    f"Hi 本週你的新球友來了！\n"
                    f"→ 點此查看 {APP_URL}/dashboard/group/{group.id}\n"
                    f"這週你有 {len(others)} 位新球友！\n"
                    f"{host_note}"
                )
            else:
                text = (
                    f"🎉 您有一個新的群組配對！\n\n"
                    f"代號：{group.cool_name}\n"
                    f"成員：{'、'.join(others)}\n\n"
                    f"👇 進入群組對話：\n{APP_URL}/dashboard/group/{group.id}"
                )
            updates[member.id].append(NotifItem(text, [('group_match', group.id)]))

    return updates


def collect_group_message_texts(session):
    updates = defaultdict(list)
    unnotified = (
        session.query(GroupMessage)
        .filter(GroupMessage.is_notified.is_not(True))
        .options(joinedload(GroupMessage.group), joinedload(GroupMessage.sender))
        .all()
    )
    if not unnotified:
        return updates

    delivered = _delivered_map(session, 'group_message', [m.id for m in unnotified])

    by_group = defaultdict(list)
    for msg in unnotified:
        by_group[msg.group_id].append(msg)

    for group_id, msgs in by_group.items():
        group = msgs[0].group

        required_by_msg = {
            m.id: {mem.id for mem in group.members if mem.id != m.sender_id}
            for m in msgs
        }
        if all(required_by_msg[m.id] <= delivered.get(m.id, set()) for m in msgs):
            for m in msgs:
                m.is_notified = True
            continue

        for member in group.members:
            pending_msgs = [
                m for m in msgs
                if m.sender_id != member.id and member.id not in delivered.get(m.id, set())
            ]
            if not pending_msgs:
                continue
            count = len(pending_msgs)
            if count <= 3:
                lines = "\n".join(
                    f"  {m.sender.proper_name}: {_trim(m.content)}" for m in pending_msgs
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
            updates[member.id].append(
                NotifItem(text, [('group_message', m.id) for m in pending_msgs])
            )

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
    if not proposals:
        return updates

    delivered = _delivered_map(session, 'group_proposal', [p.id for p in proposals])

    for proposal in proposals:
        group = proposal.group
        required = {m.id for m in group.members}
        already = delivered.get(proposal.id, set())

        if required <= already:
            proposal.is_notified = True
            continue

        date_str = proposal.proposed_datetime.strftime('%m/%d %H:%M')
        text = (
            f"📅 群組 {group.cool_name}\n\n"
            f"{proposal.proposer.proper_name} 提議在 {date_str} 前往「{proposal.restaurant_name}」！\n\n"
            f"🔗 查看詳情: {APP_URL}/dashboard/group/{group.id}"
        )
        for member in group.members:
            if member.id in already:
                continue
            updates[member.id].append(NotifItem(text, [('group_proposal', proposal.id)]))

    return updates


_COLLECTORS = [
    collect_new_match_texts,
    collect_unread_message_texts,
    collect_date_proposal_texts,
    collect_confirmed_date_proposal_texts,
    collect_new_group_match_texts,
    collect_group_message_texts,
    collect_group_proposal_texts,
]


def process_all_notifications(session):
    dev = settings.is_dev

    all_notifications: dict[int, list[NotifItem]] = defaultdict(list)
    for collector in _COLLECTORS:
        for uid, items in collector(session).items():
            all_notifications[uid].extend(items)

    if not all_notifications:
        return

    # Persist any legacy "fully notified" flags collectors flipped for rows
    # that turned out to already have every recipient delivered.
    session.commit()

    line_bot_api = LineBotApi(line_bot_helper.configuration.access_token)

    now = datetime.now(timezone.utc)

    # Eager-load all members with line_info in one query to avoid lazy-loads
    # after the commit (which expires all ORM objects).
    user_ids = list(all_notifications.keys())
    members = (
        session.query(Member)
        .filter(Member.id.in_(user_ids))
        .options(joinedload(Member.line_info))
        .all()
    )
    members_by_id = {m.id: m for m in members}

    for user_id_db, items in all_notifications.items():

        user = members_by_id.get(user_id_db)
        if not user:
            continue

        # Silence window: skip if user was active on the dashboard recently.
        # Nothing is recorded as delivered here, so this batch is retried
        # (only for this user) on the next run instead of being lost.
        if user.last_seen_at and (now - user.last_seen_at).total_seconds() < _SILENCE_WINDOW_SECONDS:
            continue

        if dev:
            target_line_id = settings.LINE_TEST_USER_ID
        else:
            if not user.line_info:
                continue
            target_line_id = user.line_info.user_id

        texts = [item.text for item in items]

        # LINE allows max 5 messages per push; bundle overflow into a summary
        if len(texts) <= 5:
            line_messages = [TextMessage(text=t) for t in texts]
        else:
            line_messages = [TextMessage(text=t) for t in texts[:4]]
            line_messages.append(TextMessage(text=f"⋯ 還有 {len(texts) - 4} 則通知，請登入查看。"))

        logging.info("Sending %d msgs to user %s", len(line_messages), user.id)

        try:
            line_bot_api.push_message(target_line_id, messages=line_messages)
        except LineBotApiError as e:
            if e.status_code == 429:
                logging.error(
                    "LINE monthly quota exceeded — notifications halted. user_id=%s",
                    user.id,
                    exc_info=True,
                )
            else:
                logging.error(
                    "Failed to push LINE message to user %s: %s", user.id, e, exc_info=True
                )
            continue
        except Exception as e:
            logging.error(
                "Unexpected error pushing LINE message to user %s: %s", user.id, e, exc_info=True
            )
            continue

        # Only now that the push has actually succeeded do we record delivery,
        # so a failed push is retried on the next run without re-notifying
        # whichever other recipient of the same event already got theirs.
        user.last_notification_sent_at = now
        _record_delivery(session, user_id_db, items)
        session.commit()

    # Second pass: now that this run's successful sends are recorded, flip the
    # legacy per-row flags for any event whose every recipient is delivered.
    for collector in _COLLECTORS:
        collector(session)
    session.commit()
