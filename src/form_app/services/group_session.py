"""
Group session lifecycle service (Phase D).

Handles:
- Opening Phase 4 (FEEDBACK) after a meetup has passed
- Closing expired sessions: ghost detection, no-show detection,
  points award, hibernation check
- 24-hour meetup reminders
- Observer wake-up notifications
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from linebot import LineBotApi
from linebot.models import TextSendMessage
from sqlalchemy.orm import Session

from form_app.config import settings
from form_app.extensions import line_bot_helper
from form_app.models import (
    ActivityLabel, GroupBadge, GroupMatching, GroupMatchingStatus,
    GroupMembership, GroupMessage, Member, MemberSessionLabel,
)
from form_app.services.group_matching import compute_activity_label

# How long after meet_time before Phase 4 opens (give the meetup time to finish)
_FEEDBACK_DELAY_HOURS = 4


# ── Low-level LINE push ───────────────────────────────────────────────────────

def _push(member: Member, text: str, line_bot_api: LineBotApi) -> None:
    """Push a single text message to a member via LINE. Silently skips if no LINE id."""
    if settings.is_dev:
        target = settings.LINE_TEST_USER_ID
    else:
        target = member.line_info.user_id if member.line_info else None
    if not target:
        return
    try:
        line_bot_api.push_message(target, TextSendMessage(text=text))
    except Exception as e:
        print(f"[group_session] LINE push failed for member {member.id}: {e}")


def _make_api() -> LineBotApi:
    return LineBotApi(line_bot_helper.configuration.access_token)


# ── Phase 4: open feedback ────────────────────────────────────────────────────

def open_group_feedback(session: Session) -> list[int]:
    """
    Transition ACTIVE groups whose meetup time has passed to FEEDBACK status
    and notify members via LINE.

    Returns list of group IDs transitioned.
    """
    cutoff = datetime.now() - timedelta(hours=_FEEDBACK_DELAY_HOURS)

    candidates = (
        session.query(GroupMatching)
        .filter(
            GroupMatching.status == GroupMatchingStatus.ACTIVE.value,
            GroupMatching.meet_time.isnot(None),
            GroupMatching.meet_time <= cutoff,
        )
        .all()
    )

    if not candidates:
        return []

    line_bot_api = _make_api()
    transitioned: list[int] = []

    for group in candidates:
        group.status = GroupMatchingStatus.FEEDBACK

        chat_url = f"{settings.APP_URL}/dashboard/group/{group.id}"
        text = (
            f"💬 【{group.cool_name}】的聚會結束囉！\n\n"
            f"夥伴們是不是超棒？趁著記憶猶新，快去送個溫暖的祝福勳章吧！✨\n\n"
            f"👇 前往評分：\n{chat_url}"
        )
        for gm in group.memberships:
            if gm.member:
                _push(gm.member, text, line_bot_api)

        transitioned.append(group.id)

    session.flush()
    return transitioned


# ── Day-15 close: ghost / no-show / points / hibernation ─────────────────────

def _detect_ghosts(memberships: list[GroupMembership]) -> set[int]:
    """Return member_ids judged as ghosts (message_count==0 AND not clicked wish)."""
    return {
        gm.member_id
        for gm in memberships
        if gm.message_count == 0 and not gm.clicked_wish_button
    }


def _detect_no_shows(
    group: GroupMatching,
    ghost_ids: set[int],
    session: Session,
) -> set[int]:
    """
    Return member_ids judged as no-shows based on Phase-4 badge votes.
    Only runs when group had a scheduled meetup.
    Ghosts are excluded from both voting and being voted on.
    """
    if not group.meet_time:
        return set()

    active_member_ids = {
        gm.member_id for gm in group.memberships if gm.member_id not in ghost_ids
    }
    n_active = len(active_member_ids)
    if n_active < 2:
        return set()

    # Count NO_SHOW badges per target from non-ghost voters
    no_show_counts: dict[int, int] = {}
    badges = (
        session.query(GroupBadge)
        .filter(
            GroupBadge.group_id == group.id,
            GroupBadge.badge_type == "NO_SHOW",
        )
        .all()
    )
    for badge in badges:
        if badge.from_member_id in ghost_ids:
            continue  # ghost votes don't count
        if badge.to_member_id not in active_member_ids:
            continue
        no_show_counts[badge.to_member_id] = no_show_counts.get(badge.to_member_id, 0) + 1

    # Threshold: ≥2 votes for 3+ person group, ≥1 for 2-person group
    threshold = 1 if n_active == 2 else 2
    return {mid for mid, count in no_show_counts.items() if count >= threshold}


def _award_points(member: Member, delta: int, session: Session) -> None:
    """Add companion_score and update activity_label (preserves OBSERVER status)."""
    member.companion_score = (member.companion_score or 0) + delta
    if member.activity_label != ActivityLabel.OBSERVER:
        member.activity_label = compute_activity_label(member.companion_score)


def _check_and_apply_hibernation(
    member: Member, current_label: MemberSessionLabel, session: Session
) -> bool:
    """
    Return True and apply OBSERVER status if the member has two consecutive bad sessions.
    A "bad session" is GHOST or NO_SHOW.
    """
    if current_label == MemberSessionLabel.PERFECT:
        return False

    # Find the most recent PREVIOUS closed session label for this member
    prev = (
        session.query(GroupMembership)
        .join(GroupMatching, GroupMembership.group_id == GroupMatching.id)
        .filter(
            GroupMembership.member_id == member.id,
            GroupMembership.final_label.isnot(None),
            GroupMatching.status == GroupMatchingStatus.CLOSED.value,
        )
        .order_by(GroupMatching.expires_at.desc())
        .first()
    )

    if prev is None:
        return False  # first bad session — no hibernation yet

    if prev.final_label not in (MemberSessionLabel.GHOST, MemberSessionLabel.NO_SHOW):
        return False

    # Two consecutive bad sessions → hibernate
    member.observer_offense_count = (member.observer_offense_count or 0) + 1
    member.observer_since = datetime.now(timezone.utc)
    member.activity_label = ActivityLabel.OBSERVER
    return True


def _send_hibernation_notice(member: Member, line_bot_api: LineBotApi) -> None:
    sleep_days = 14 if member.observer_offense_count == 1 else 28
    text = (
        f"🍂 {member.name}，最近生活是不是太忙碌了呢？\n\n"
        f"夥伴們都說「這次好可惜沒能見到你」呢！"
        f"為了不讓你一直接到通知而感到壓力，Citylove 貼心地幫你安排了 {sleep_days} 天的落葉休眠假。\n\n"
        f"這幾週就先好好忙你的生活、好好休息。"
        f"等忙完了、想出門散散心時，隨時歡迎回來按鈕發芽，我們再一起開心地出發喔！🌱"
    )
    _push(member, text, line_bot_api)


def close_expired_groups(session: Session) -> dict:
    """
    Find expired groups and process them:
      1. Ghost detection
      2. No-show detection (if meetup was scheduled)
      3. Assign final_labels to all memberships
      4. Award companion_score points
      5. Hibernation check
      6. Mark group CLOSED

    Returns a summary dict for logging.
    """
    now = datetime.now()
    expired = (
        session.query(GroupMatching)
        .filter(
            GroupMatching.status.in_([
                GroupMatchingStatus.ACTIVE.value,
                GroupMatchingStatus.FEEDBACK.value,
            ]),
            GroupMatching.expires_at <= now,
        )
        .all()
    )

    if not expired:
        return {"closed": 0}

    line_bot_api = _make_api()
    closed_count = 0
    hibernation_count = 0

    for group in expired:
        memberships = group.memberships
        if not memberships:
            group.status = GroupMatchingStatus.CLOSED
            continue

        ghost_ids = _detect_ghosts(memberships)
        no_show_ids = _detect_no_shows(group, ghost_ids, session)

        has_meetup = group.meet_time is not None

        for gm in memberships:
            member = gm.member
            if not member:
                continue

            # Determine this session's label
            if gm.member_id in ghost_ids:
                label = MemberSessionLabel.GHOST
            elif gm.member_id in no_show_ids:
                label = MemberSessionLabel.NO_SHOW
            else:
                label = MemberSessionLabel.PERFECT

            gm.final_label = label

            # Award opener bonus (+2) — regardless of attendance
            if group.opener_member_id == member.id:
                _award_points(member, 2, session)

            # Award attendance bonus (+3) — only if meetup happened and member attended
            if has_meetup and label == MemberSessionLabel.PERFECT:
                _award_points(member, 3, session)

            # Hibernation check
            if _check_and_apply_hibernation(member, label, session):
                hibernation_count += 1
                _send_hibernation_notice(member, line_bot_api)

        group.status = GroupMatchingStatus.CLOSED
        closed_count += 1

    session.flush()
    return {"closed": closed_count, "hibernations": hibernation_count}


# ── 24-hour meetup reminder ───────────────────────────────────────────────────

def send_meetup_reminders(session: Session) -> int:
    """
    Send a 24-hour-before reminder for groups with an upcoming meetup.
    Uses meetup_reminder_sent_at to prevent double-sending.
    Returns the number of groups that received reminders.
    """
    now = datetime.now(timezone.utc)
    window_start = now
    window_end = now + timedelta(hours=24)

    candidates = (
        session.query(GroupMatching)
        .filter(
            GroupMatching.status == GroupMatchingStatus.ACTIVE.value,
            GroupMatching.meet_time.isnot(None),
            GroupMatching.meetup_reminder_sent_at.is_(None),
        )
        .all()
    )

    line_bot_api = _make_api()
    sent_count = 0

    for group in candidates:
        # meet_time may be naive; normalise for comparison
        mt = group.meet_time
        if mt.tzinfo is None:
            mt = mt.replace(tzinfo=timezone.utc)

        if not (window_start <= mt <= window_end):
            continue

        meet_str = group.meet_time.strftime('%m/%d (%a) %H:%M')
        maps_url = (
            "https://www.google.com/maps/search/"
            + group.meet_location.replace(' ', '+')
        )

        text = (
            f"🧭 Citylove 溫柔小鬧鐘 ⏰\n\n"
            f"嗨大家！生活忙碌之餘，也別忘了明天的期待唷！"
            f"我們的同行小約定即將在 24 小時後啟航：\n\n"
            f"📍 集合地點：{group.meet_location}\n"
            f"     🗺️ 一鍵導航：{maps_url}\n"
            f"📅 見面時間：{meet_str}\n"
            + (f"💬 {group.meet_notes}\n" if group.meet_notes else "")
            + f"\n期待相見！出門前記得檢查手機電量，"
            f"如果有任何突發狀況，隨時在聊天室跟夥伴說一聲唷！🙌"
        )

        # Only send to non-ghost members (message_count > 0 OR clicked wish)
        for gm in group.memberships:
            if gm.member and not gm.is_ghost:
                _push(gm.member, text, line_bot_api)

        group.meetup_reminder_sent_at = now
        sent_count += 1

    session.flush()
    return sent_count


# ── Observer wake-up ──────────────────────────────────────────────────────────

def send_observer_wakeups(session: Session) -> int:
    """
    Send wake-up LINE messages to observers whose sleep period has ended today.
    Does NOT reactivate them — they must click the link themselves.
    Returns number of messages sent.
    """
    today = datetime.now(timezone.utc).date()

    observers = (
        session.query(Member)
        .filter(
            Member.activity_label == ActivityLabel.OBSERVER.value,
            Member.observer_since.isnot(None),
        )
        .all()
    )

    line_bot_api = _make_api()
    sent = 0

    for member in observers:
        sleep_days = 14 if (member.observer_offense_count or 0) <= 1 else 28
        os = member.observer_since
        if os.tzinfo is None:
            os = os.replace(tzinfo=timezone.utc)
        wake_date = (os + timedelta(days=sleep_days)).date()

        if wake_date > today:
            continue  # not time yet

        reactivate_url = f"{settings.APP_URL}/dashboard/reactivate"
        text = (
            f"🌱 嗨 {member.name}，最近生活忙碌得開心嗎？\n\n"
            f"你的落葉休眠假期今天正式結束囉！"
            f"Citylove 已經幫你充飽電，隨時準備好再次陪你出門探索生活。\n\n"
            f"當你調整好步調、想和新朋友一起出門散散心時，"
            f"請點擊下方連結，我們就會把你加入下週一的同行盲盒配對池唷！✨\n\n"
            f"☕ 牽成這個願望，一起出發吧！\n{reactivate_url}"
        )
        _push(member, text, line_bot_api)
        sent += 1

    return sent
