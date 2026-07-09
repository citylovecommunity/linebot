"""
Group session formation service.

Responsible for:
- Determining eligible members for group formation
- Scoring age/region compatibility
- Applying priority grouping rules (2F+2M > 1F+2M > 2F+1M > 1F+1M > female-only)
- Persisting GroupMatching + GroupMembership records
- Sending LINE formation notifications
"""
from __future__ import annotations

from datetime import datetime, timedelta
from itertools import combinations, product
from typing import Optional

from linebot.models import TextSendMessage
from sqlalchemy.orm import Session

from form_app.config import settings
from form_app.extensions import line_bot_helper
from form_app.models import (
    ActivityLabel, COMPANION_AVATARS,
    GroupMatching, GroupMembership, GroupMatchingStatus, GroupMessage,
    Line_Info, Member, assign_session_avatars,
)
from form_app.services.cool_name import generate_funny_name
from form_app.services.scoring import UserProfileAdapter

# ── Region definitions ────────────────────────────────────────────────────────

# Maps each datable_place keyword to a macro-region label.
_PLACE_TO_REGION: dict[str, str] = {
    "大台北地區": "北區",
    "台北": "北區",
    "新北": "北區",
    "基隆": "北區",
    "宜蘭": "北區",
    "桃園": "北區",
    "新竹": "北區",
    "台中": "中區",
    "彰雲投苗嘉": "中區",
    "彰化": "中區",
    "台南高雄": "南區",
    "台南": "南區",
    "高雄": "南區",
    "花蓮台東": "東區",
    "花蓮": "東區",
    "台東": "東區",
}

# Regions that can mix when the same-region pool is insufficient.
# South and East are considered neighbors; North and Central do not cross.
_NEIGHBOR_REGIONS: dict[str, list[str]] = {
    "北區": ["北區"],
    "中區": ["中區"],
    "南區": ["南區", "東區"],
    "東區": ["東區", "南區"],
}

# ── Campaign priority rules ─────────────────────────────────────────────────────

# Campaign whose signups get a priority group-formation pass before the general pool.
PICKLE_BALL_CAMPAIGN = "pickle_ball"

# "Enough activity" bar for the male side of a pickle_ball group.
_PICKLE_BALL_ACTIVE_LABELS = (ActivityLabel.ACTIVE_TRAVELER, ActivityLabel.SUPER_TRAVELER)

# Posted into the group chat as a system message as soon as a pickle_ball
# group is formed (in addition to the LINE formation push).
PICKLE_BALL_CHAT_ANNOUNCEMENT = (
    "Hi 🏓 歡迎來到城遇匹克球季\n"
    "本次任務內容如下：https://join.citylove.tw/pickleball_instructions\n"
    "一起約打球吧～"
)

# ── Label thresholds ──────────────────────────────────────────────────────────

LABEL_THRESHOLDS = [
    (15, ActivityLabel.SUPER_TRAVELER),
    (5,  ActivityLabel.ACTIVE_TRAVELER),
    (0,  ActivityLabel.TRAVELER),
]


def compute_activity_label(score: int) -> ActivityLabel:
    """Return the label earned by a companion score (ignores OBSERVER — set separately)."""
    for threshold, label in LABEL_THRESHOLDS:
        if score >= threshold:
            return label
    return ActivityLabel.TRAVELER


# ── Region helpers ────────────────────────────────────────────────────────────

def compute_region_from_places_str(places_str: str) -> Optional[str]:
    """Derive a macro-region label from a raw '可約會地區' comma/、separated string."""
    if not places_str or places_str.strip() in ('', '不設限', '不限'):
        return None
    region_counts: dict[str, int] = {}
    for place in places_str.replace('、', ',').split(','):
        place = place.strip()
        for keyword, region in _PLACE_TO_REGION.items():
            if keyword in place:
                region_counts[region] = region_counts.get(region, 0) + 1
                break
    if not region_counts:
        return None
    return max(region_counts, key=lambda r: region_counts[r])


def get_member_region(member: Member) -> Optional[str]:
    """
    Derive the primary region from a member's datable_place list.
    Returns the most common region among their listed places, or None if unknown.
    """
    adapter = UserProfileAdapter.from_member(member)
    places = adapter.datable_place  # set of strings
    if not places or "不設限" in places:
        return None  # will be matched into any region

    region_counts: dict[str, int] = {}
    for place in places:
        for keyword, region in _PLACE_TO_REGION.items():
            if keyword in place:
                region_counts[region] = region_counts.get(region, 0) + 1
                break

    if not region_counts:
        return None
    return max(region_counts, key=lambda r: region_counts[r])


def regions_can_mix(r1: Optional[str], r2: Optional[str]) -> bool:
    """True when two region labels are the same or neighboring."""
    if r1 is None or r2 is None:
        return True  # 不設限 members can go anywhere
    return r2 in _NEIGHBOR_REGIONS.get(r1, [r1])


# ── Age compatibility ─────────────────────────────────────────────────────────

def _birth_year(member: Member) -> int:
    if member.birthday:
        return member.birthday.year
    adapter = UserProfileAdapter.from_member(member)
    return adapter.birth_year or 0


def age_compat_score(female: Member, male: Member) -> int:
    """
    Score age compatibility between a female and a male.
    Higher is better: Golden (10) > Close (7) > Comfortable (5) > Possible (1).
    Special rule: female 43+ allows males up to 19 years older (score 5).
    """
    current_year = datetime.now().year
    fy = _birth_year(female)
    my = _birth_year(male)
    if fy == 0 or my == 0:
        return 3  # unknown age — neutral score

    age_f = current_year - fy
    age_m = current_year - my
    gap = age_m - age_f  # positive = male is older

    if age_f >= 43 and 1 <= gap <= 19:
        return 5

    abs_gap = abs(gap)
    if 3 <= abs_gap <= 5:
        return 10
    if 0 <= abs_gap <= 2:
        return 7
    if 6 <= abs_gap <= 8:
        return 5
    return 1


def _group_score(females: list[Member], males: list[Member]) -> float:
    """Average age-compat score across all cross-gender pairs in a group."""
    pairs = list(product(females, males))
    if not pairs:
        return 5.0  # neutral for same-sex groups
    return sum(age_compat_score(f, m) for f, m in pairs) / len(pairs)


def _pairwise_score_matrix(
    females: list[Member], males: list[Member]
) -> dict[tuple[int, int], int]:
    """Precompute age_compat_score for every (female, male) pair once — avoids
    recomputing the same score millions of times inside _best_2f2m's nested
    combinations search."""
    return {(f.id, m.id): age_compat_score(f, m) for f in females for m in males}


# ── Eligibility ───────────────────────────────────────────────────────────────

def get_eligible_group_pool(session: Session) -> tuple[list[Member], list[Member]]:
    """
    Return (females, males) eligible for group formation this cycle.

    Eligibility:
    - Active, non-test, has introduction_link, has Line_Info
    - Not an Observer (🍂)
    - Female cadence: < 3 sessions in last 14 days
    - Male cadence: < 1 session in last 7 days
    """
    from sqlalchemy.sql.expression import exists
    from sqlalchemy import func
    from datetime import date

    today = date.today()
    now = datetime.now()
    cutoff_f = now - timedelta(days=14)
    cutoff_m = now - timedelta(days=7)

    base = (
        session.query(Member)
        .filter(
            Member.is_member_active == True,
            Member.is_test == False,
            Member.introduction_link != None,
            Member.introduction_link != '',
            exists().where(Line_Info.phone_number == Member.phone_number),
            Member.activity_label != ActivityLabel.OBSERVER.value,
            (Member.expiration_date == None) | (Member.expiration_date >= today),
            (Member.matching_start_date == None) | (Member.matching_start_date <= today),
            (Member.matching_end_date == None) | (Member.matching_end_date >= today),
        )
        .all()
    )

    if not base:
        return [], []

    female_ids = {m.id for m in base if m.gender == 'F'}
    male_ids   = {m.id for m in base if m.gender == 'M'}

    # Batch-query session counts — 2 queries instead of one per member
    f_counts: dict[int, int] = {}
    if female_ids:
        rows = (
            session.query(GroupMembership.member_id, func.count())
            .join(GroupMatching)
            .filter(
                GroupMembership.member_id.in_(female_ids),
                GroupMembership.is_referral == False,
                GroupMatching.created_at >= cutoff_f,
            )
            .group_by(GroupMembership.member_id)
            .all()
        )
        f_counts = {mid: cnt for mid, cnt in rows}

    m_counts: dict[int, int] = {}
    if male_ids:
        rows = (
            session.query(GroupMembership.member_id, func.count())
            .join(GroupMatching)
            .filter(
                GroupMembership.member_id.in_(male_ids),
                GroupMembership.is_referral == False,
                GroupMatching.created_at >= cutoff_m,
            )
            .group_by(GroupMembership.member_id)
            .all()
        )
        m_counts = {mid: cnt for mid, cnt in rows}

    females = [m for m in base if m.gender == 'F' and f_counts.get(m.id, 0) < 3]
    males   = [m for m in base if m.gender == 'M' and m_counts.get(m.id, 0) < 1]

    return females, males


# ── Best-pick helpers ─────────────────────────────────────────────────────────

def _best_2f2m(
    females: list[Member], males: list[Member]
) -> tuple[list[Member], list[Member]]:
    """Return the (2 females, 2 males) combination with the highest group score."""
    if not females or not males:
        return females[:2], males[:2]

    # Precompute every pairwise score once — the search below evaluates
    # O(|females|^2 * |males|^2) quartets, so recomputing age_compat_score()
    # per quartet (as the naive version did) is millions of redundant calls
    # on large pools. A lookup table turns each quartet check into 4 dict
    # lookups + a sum, which is what makes this search tractable at scale.
    matrix = _pairwise_score_matrix(females, males)

    best_score = -1.0
    best: tuple[list[Member], list[Member]] = (females[:2], males[:2])

    for f1, f2 in combinations(females, 2):
        for m1, m2 in combinations(males, 2):
            score = (
                matrix[(f1.id, m1.id)] + matrix[(f1.id, m2.id)] +
                matrix[(f2.id, m1.id)] + matrix[(f2.id, m2.id)]
            )
            if score > best_score:
                best_score = score
                best = ([f1, f2], [m1, m2])

    return best


def _best_males_for(females: list[Member], males: list[Member], count: int) -> list[Member]:
    """Return the top `count` males ranked by avg age compat with the given females."""
    scored = sorted(
        males,
        key=lambda m: sum(age_compat_score(f, m) for f in females) / len(females),
        reverse=True,
    )
    return scored[:count]


def _best_females_for(males: list[Member], females: list[Member], count: int) -> list[Member]:
    """Return the top `count` females ranked by avg age compat with the given males."""
    scored = sorted(
        females,
        key=lambda f: sum(age_compat_score(f, m) for m in males) / len(males),
        reverse=True,
    )
    return scored[:count]


# ── Core formation algorithm ──────────────────────────────────────────────────

def _form_groups_from_pool(
    females: list[Member], males: list[Member], region: Optional[str]
) -> list[tuple[list[Member], list[Member]]]:
    """
    Form groups from a regional pool following the priority rules.
    Returns list of (females_in_group, males_in_group) tuples.
    Hard rule: never 1F + 3M.
    """
    groups: list[tuple[list[Member], list[Member]]] = []
    avail_f = list(females)
    avail_m = list(males)

    # Priority 1: 2F + 2M
    while len(avail_f) >= 2 and len(avail_m) >= 2:
        f_pair, m_pair = _best_2f2m(avail_f, avail_m)
        groups.append((f_pair, m_pair))
        for f in f_pair:
            avail_f.remove(f)
        for m in m_pair:
            avail_m.remove(m)

    # After Priority 1, either len(f) < 2 or len(m) < 2.
    # Priority 2: 2F+1M
    if len(avail_f) >= 2 and len(avail_m) == 1:
        f_pair = _best_females_for(avail_m, avail_f, 2)
        groups.append((f_pair, avail_m[:]))
        for f in f_pair:
            avail_f.remove(f)
        avail_m.clear()

    # Priority 2: 1F+2M (enforce 1F+2M, never 1F+3M)
    elif len(avail_f) == 1 and len(avail_m) >= 2:
        m_pair = _best_males_for(avail_f, avail_m, 2)
        groups.append((avail_f[:], m_pair))
        avail_f.clear()
        for m in m_pair:
            avail_m.remove(m)
        # Remaining males (if any) wait for next cycle

    # Priority 3: 1F+1M
    elif len(avail_f) == 1 and len(avail_m) == 1:
        groups.append((avail_f[:], avail_m[:]))
        avail_f.clear()
        avail_m.clear()

    # Priority 4: remaining females → all-female groups (2–4 people)
    while len(avail_f) >= 2:
        size = min(4, len(avail_f))
        group_f = avail_f[:size]
        groups.append((group_f, []))
        avail_f = avail_f[size:]

    return groups


def _bucket_by_region(
    members: list[Member],
) -> tuple[dict[str, list[Member]], list[Member]]:
    """
    Split members into regional buckets.
    Returns (buckets_by_region, unrestricted_members).
    """
    buckets: dict[str, list[Member]] = {"北區": [], "中區": [], "南區": [], "東區": []}
    unrestricted: list[Member] = []

    for member in members:
        region = get_member_region(member)
        if region and region in buckets:
            buckets[region].append(member)
        else:
            unrestricted.append(member)

    return buckets, unrestricted


def _form_pickleball_groups(
    females: list[Member], males: list[Member]
) -> tuple[list[tuple[list[Member], list[Member], Optional[str]]], set[int], set[int]]:
    """
    Priority pass, run before the general region loop: pair pickle_ball-campaign
    females with sufficiently active males (ACTIVE_TRAVELER+), region-compatible,
    strictly as 2F+2M groups (no 1F/female-only fallback here — any pickle_ball
    leftovers simply flow into the general pass like any other member).

    Returns (groups, consumed_female_ids, consumed_male_ids) where each group is
    a (females, males, region) tuple.
    """
    pickle_f = [f for f in females if f.join_campaign == PICKLE_BALL_CAMPAIGN]
    active_m = [m for m in males if m.activity_label in _PICKLE_BALL_ACTIVE_LABELS]

    if len(pickle_f) < 2 or len(active_m) < 2:
        return [], set(), set()

    f_buckets, unrestricted_f = _bucket_by_region(pickle_f)
    m_buckets, unrestricted_m = _bucket_by_region(active_m)

    groups: list[tuple[list[Member], list[Member], Optional[str]]] = []
    consumed_f: set[int] = set()
    consumed_m: set[int] = set()

    for region in ("北區", "中區", "南區", "東區"):
        region_f = f_buckets[region] + unrestricted_f
        region_m = m_buckets[region] + unrestricted_m
        for neighbor in _NEIGHBOR_REGIONS.get(region, []):
            if neighbor != region:
                region_f = region_f + f_buckets.get(neighbor, [])
                region_m = region_m + m_buckets.get(neighbor, [])

        seen_f: set[int] = set()
        seen_m: set[int] = set()
        avail_f = [
            f for f in region_f
            if f.id not in consumed_f and f.id not in seen_f and not seen_f.add(f.id)  # type: ignore[func-returns-value]
        ]
        avail_m = [
            m for m in region_m
            if m.id not in consumed_m and m.id not in seen_m and not seen_m.add(m.id)  # type: ignore[func-returns-value]
        ]

        while len(avail_f) >= 2 and len(avail_m) >= 2:
            f_pair, m_pair = _best_2f2m(avail_f, avail_m)
            groups.append((f_pair, m_pair, region))
            for f in f_pair:
                avail_f.remove(f)
                consumed_f.add(f.id)
            for m in m_pair:
                avail_m.remove(m)
                consumed_m.add(m.id)

    return groups, consumed_f, consumed_m


def _pick_opener(females: list[Member], session: Session) -> Optional[Member]:
    """Pick the female in the group who has been opener least recently."""
    if not females:
        return None
    from sqlalchemy import func
    last_opener: dict[int, Optional[datetime]] = {}
    for f in females:
        ts = (
            session.query(func.max(GroupMatching.created_at))
            .filter(GroupMatching.opener_member_id == f.id)
            .scalar()
        )
        last_opener[f.id] = ts
    return min(females, key=lambda f: last_opener[f.id] or datetime.min)


# ── Persistence ───────────────────────────────────────────────────────────────

def _create_group(
    females: list[Member],
    males: list[Member],
    region: Optional[str],
    session: Session,
    source_campaign: Optional[str] = None,
    is_draft: bool = False,
) -> GroupMatching:
    """Persist one GroupMatching with memberships and return it."""
    all_members = females + males
    avatars = assign_session_avatars(len(all_members))
    opener = _pick_opener(females, session) if females else None

    group = GroupMatching(
        cool_name=generate_funny_name(),
        region=region,
        source_campaign=source_campaign,
        status=GroupMatchingStatus.DRAFT if is_draft else GroupMatchingStatus.ACTIVE,
        # Drafts stay silent (is_notified=True) until an admin approves them,
        # mirroring Matching.is_match_notified for DRAFT 1-on-1 matches.
        is_notified=is_draft,
        expires_at=datetime.now() + timedelta(days=15),
        opener_member_id=opener.id if opener else None,
        memberships=[
            GroupMembership(member_id=m.id, session_avatar=avatars[i])
            for i, m in enumerate(all_members)
        ],
    )
    session.add(group)

    if source_campaign == PICKLE_BALL_CAMPAIGN and opener:
        # Flush so `group.id` exists for the message FK, then post the
        # welcome announcement as the group's opening system message.
        session.flush()
        announcement = GroupMessage(
            group_id=group.id,
            sender_id=opener.id,
            content=PICKLE_BALL_CHAT_ANNOUNCEMENT,
            is_system_notification=True,
            # Already covered by the dedicated "新球友" LINE push below —
            # don't also fire the generic "you have unread messages" push.
            is_notified=True,
        )
        session.add(announcement)
        session.flush()
        group.last_message_id = announcement.id

    return group


# ── LINE notification ─────────────────────────────────────────────────────────

def _notify_group_formed(group: GroupMatching, session: Session) -> None:
    """Push a LINE formation notification to every member of the group."""
    from linebot import LineBotApi

    line_bot_api = LineBotApi(line_bot_helper.configuration.access_token)
    dev = settings.is_dev
    chat_url = f"{settings.APP_URL}/dashboard/group/{group.id}"

    for membership in group.memberships:
        member = membership.member
        if not member:
            continue

        opener_name = (
            group.opener.name if group.opener_member_id and group.opener else "夥伴"
        )
        partner_names = ", ".join(
            m.member.name for m in group.memberships if m.member_id != member.id
        )
        is_opener = group.opener_member_id == member.id

        if is_opener:
            intro = (
                f"🎉 Citylove 新的同行局【{group.cool_name}】開始了！\n\n"
                f"這次的夥伴有：{partner_names}\n\n"
                f"🎤 這局的麥克風先交給你開球！拋個你想完成的事、想去的地方或美食吧！✨\n\n"
                f"👇 前往聊天室：\n{chat_url}"
            )
        else:
            intro = (
                f"🎉 Citylove 新的同行局【{group.cool_name}】開始了！\n\n"
                f"這次的夥伴有：{partner_names}\n\n"
                f"🎤 {opener_name} 會先開球，你也可以隨時自由發言！✨\n\n"
                f"👇 前往聊天室：\n{chat_url}"
            )

        target = settings.LINE_TEST_USER_ID if dev else (
            member.line_info.user_id if member.line_info else None
        )
        if not target:
            continue

        try:
            line_bot_api.push_message(target, TextSendMessage(text=intro))
        except Exception as e:
            print(f"[group_matching] Failed to notify member {member.id}: {e}")

    group.is_notified = True


# ── Public entry point ────────────────────────────────────────────────────────

def form_groups(session: Session, is_draft: bool = False) -> list[GroupMatching]:
    """
    Main entry point. Forms groups for this cycle and persists them.
    Does NOT commit — caller is responsible for session.commit().
    Returns the list of newly created GroupMatching objects.

    When is_draft is True, groups are created with status=DRAFT and stay
    silent (no LINE notification) until an admin approves them.
    """
    females, males = get_eligible_group_pool(session)

    if not females:
        return []

    created: list[GroupMatching] = []

    # Priority pass: pickle_ball-campaign females + sufficiently active males,
    # region-compatible, formed before the general pool so campaign members
    # get first pick. Any pickle_ball leftovers simply flow into the general pass.
    pb_groups, consumed_f_ids, consumed_m_ids = _form_pickleball_groups(females, males)
    for group_f, group_m, region in pb_groups:
        group = _create_group(
            group_f, group_m, region, session,
            source_campaign=PICKLE_BALL_CAMPAIGN, is_draft=is_draft,
        )
        created.append(group)

    females = [f for f in females if f.id not in consumed_f_ids]
    males = [m for m in males if m.id not in consumed_m_ids]

    female_buckets, unrestricted_f = _bucket_by_region(females)
    male_buckets, unrestricted_m = _bucket_by_region(males)

    for region in ("北區", "中區", "南區", "東區"):
        region_f = female_buckets[region] + unrestricted_f
        region_m = male_buckets[region] + unrestricted_m

        # Also include neighbors when pool is thin
        for neighbor in _NEIGHBOR_REGIONS.get(region, []):
            if neighbor != region:
                region_f = region_f + female_buckets.get(neighbor, [])
                region_m = region_m + male_buckets.get(neighbor, [])

        # Deduplicate (unrestricted members may have been added multiple times)
        seen_f: set[int] = set()
        seen_m: set[int] = set()
        deduped_f = [f for f in region_f if f.id not in seen_f and not seen_f.add(f.id)]  # type: ignore[func-returns-value]
        deduped_m = [m for m in region_m if m.id not in seen_m and not seen_m.add(m.id)]  # type: ignore[func-returns-value]

        groups_this_region = _form_groups_from_pool(deduped_f, deduped_m, region)

        for group_f, group_m in groups_this_region:
            group = _create_group(group_f, group_m, region, session, is_draft=is_draft)
            created.append(group)

            # Remove used members from unrestricted pool so they aren't reused
            for f in group_f:
                if f in unrestricted_f:
                    unrestricted_f.remove(f)
                else:
                    female_buckets[region] = [
                        x for x in female_buckets.get(region, []) if x.id != f.id
                    ]
            for m in group_m:
                if m in unrestricted_m:
                    unrestricted_m.remove(m)
                else:
                    male_buckets[region] = [
                        x for x in male_buckets.get(region, []) if x.id != m.id
                    ]

    # Flush so group IDs are available (caller is responsible for commit + notifications)
    session.flush()

    return created
