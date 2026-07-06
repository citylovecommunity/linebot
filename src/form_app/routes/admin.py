import uuid
from datetime import datetime, date, timedelta, timezone

from flask import Blueprint, jsonify, render_template, redirect, url_for, flash, request, session as flask_session
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload, defer, selectinload
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.exc import IntegrityError

# ── Redis-backed dashboard cache ───────────────────────────────────────────────
# Shared across all gunicorn workers so invalidation is consistent.
# Falls back to no-cache if REDIS_URL is not configured.
_DASHBOARD_CACHE_KEY = 'admin:dashboard_html'
_DASHBOARD_CACHE_TTL = 60  # seconds

_redis_client = None

def _get_redis():
    global _redis_client
    if _redis_client is None:
        from form_app.config import settings
        if settings.REDIS_URL:
            import redis
            _redis_client = redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                ssl_cert_reqs=None,
            )
    return _redis_client


def _invalidate_dashboard_cache():
    r = _get_redis()
    if r:
        r.delete(_DASHBOARD_CACHE_KEY)

from form_app.models import (
    ActivityLabel, Invite, Member, Matching, MatchingStatus, Message, UserMatchScore,
    DateProposal, ProposalStatus, Line_Info,
    GroupMatching, GroupMatchingStatus, GroupMembership, GroupMessage, GroupDateProposal, GroupBadge,
    LeadSubmission, LeadSubmissionStatus,
    Tag,
    assign_session_avatars,
)
from collections import defaultdict
from form_app.decorators import admin_required, developer_required
from form_app.database import get_db
from form_app.services.cool_name import generate_funny_name
from form_app.services.messaging import process_all_notifications
from form_app.services.scoring import UserProfileAdapter, calculate_match_score, get_eligible_matching_pool
from form_app.services.matching import update_unmatched_counters
from form_app.services.security import hash_password
from form_app.config import settings


bp = Blueprint('admin_bp', __name__, url_prefix='/admin')


def _populate_matchmaking_info(user_info: dict, form):
    """
    Reads matchmaking-relevant fields from the submitted form and writes them
    into user_info with the canonical Chinese keys the scoring engine expects.
    Called for both new-user creation and edit.
    """
    # --- Personal profile ---
    _set_if_present(user_info, '您目前的感情狀況', form.get('marital_status', '').strip())
    _set_if_present(user_info, '您有無小孩需要扶養', form.get('has_children', '').strip())
    _set_if_present(user_info, '會員之職業類別', form.get('job_category', '').strip())
    _set_if_present(user_info, '您的飲食習慣', form.get('diet', '').strip())
    _set_if_present(user_info, '宗教信仰', form.get('religion', '').strip())

    # --- Datable regions (multi-select checkboxes) ---
    regions = form.getlist('date_regions')
    user_info['可約會地區 (可複選)'] = ','.join(regions) if regions else ''

    # --- Hard dealbreakers (multi-select checkboxes) ---
    dealbreakers = form.getlist('dealbreakers')
    user_info['您完全無法接受的對象條件 (可複選)'] = ','.join(dealbreakers) if dealbreakers else '不設限'

    # --- Specific cannot-accept fields ---
    _set_if_present(user_info, '不能接受的飲食習慣', form.get('dealbreaker_diet', '').strip())
    _set_if_present(user_info, '無法接受之職業類別', form.get('dealbreaker_job', '').strip())
    _set_if_present(user_info, '無法接受的宗教信仰', form.get('dealbreaker_religion', '').strip())


def _set_if_present(d: dict, key: str, value: str):
    if value:
        d[key] = value


def _diagnose_unmatched(eligible_pool, draft_matchings, all_matchings, session):
    """
    Returns [(member, reason_str, candidates), ...] for eligible members absent
    from draft_matchings.  candidates is [(Member, combined_score), ...] sorted
    by score desc — all opposite-gender eligible members never previously matched
    with this person (regardless of dealbreaker status, for admin override).
    """
    from sqlalchemy import or_, and_

    draft_matched_ids = set()
    for dm in draft_matchings:
        draft_matched_ids.add(dm.subject_id)
        draft_matched_ids.add(dm.object_id)

    unmatched = [m for m in eligible_pool if m.id not in draft_matched_ids]
    if not unmatched:
        return []

    eligible_by_id = {m.id: m for m in eligible_pool}
    eligible_by_gender = defaultdict(set)
    all_eligible_ids = set()
    for m in eligible_pool:
        eligible_by_gender[m.gender].add(m.id)
        all_eligible_ids.add(m.id)

    # Historical pairs from confirmed/active/cancelled matchings (drafts excluded)
    historical_pairs = set()
    for m in all_matchings:
        historical_pairs.add((m.subject_id, m.object_id))
        historical_pairs.add((m.object_id, m.subject_id))

    # Batch-fetch all scores touching unmatched users against the eligible pool
    unmatched_ids = [m.id for m in unmatched]
    score_rows = session.query(
        UserMatchScore.source_user_id,
        UserMatchScore.target_user_id,
        UserMatchScore.score,
    ).filter(
        or_(
            and_(
                UserMatchScore.source_user_id.in_(unmatched_ids),
                UserMatchScore.target_user_id.in_(all_eligible_ids),
            ),
            and_(
                UserMatchScore.source_user_id.in_(all_eligible_ids),
                UserMatchScore.target_user_id.in_(unmatched_ids),
            ),
        )
    ).all()

    score_map = {(r.source_user_id, r.target_user_id): r.score for r in score_rows}

    results = []
    for member in unmatched:
        opposite_gender = 'F' if member.gender == 'M' else 'M'
        opposite_ids = eligible_by_gender[opposite_gender]

        if not opposite_ids:
            results.append((member, "配對池中無異性會員", []))
            continue

        # Candidates not historically paired with this member
        remaining = {oid for oid in opposite_ids if (member.id, oid) not in historical_pairs}

        if not remaining:
            results.append((member, "已與配對池內所有異性有過配對記錄", []))
            continue

        # Tally edges for reason diagnosis
        valid_count = 0
        excluded_count = 0
        no_score_count = 0

        for oid in remaining:
            s_me_them = score_map.get((member.id, oid))
            s_them_me = score_map.get((oid, member.id))

            if s_me_them is None and s_them_me is None:
                no_score_count += 1
            elif s_me_them is not None and s_them_me is not None \
                    and s_me_them > 0 and s_them_me > 0:
                valid_count += 1
            else:
                excluded_count += 1

        if no_score_count == len(remaining):
            reason = "尚未計算配對分數，請重新執行分數計算"
        elif excluded_count > 0 and valid_count == 0:
            reason = "與所有候選對象條件不符（雙方條件篩選排除）"
        else:
            reason = "部分候選對象缺少分數資料，其餘條件不符"

        # Build candidate list for manual pairing (all non-historical opposite-gender,
        # sorted by combined score desc so the best options appear first)
        candidates = []
        for oid in remaining:
            candidate = eligible_by_id.get(oid)
            if not candidate:
                continue
            s1 = score_map.get((member.id, oid)) or 0
            s2 = score_map.get((oid, member.id)) or 0
            combined = (s1 + s2) / 2
            candidates.append((candidate, combined))
        candidates.sort(key=lambda x: x[1], reverse=True)

        results.append((member, reason, candidates))

    return results


@bp.route('/dashboard')
@login_required
@admin_required
def admin_dashboard():
    cache = _get_redis()
    has_flash = bool(flask_session.get('_flashes'))
    bypass_cache = request.args.get('generated') == '1'
    if not has_flash and not bypass_cache and cache:
        cached = cache.get(_DASHBOARD_CACHE_KEY)
        if cached:
            return cached

    session = get_db()

    all_members = (
        session.query(Member)
        .options(
            defer(Member.user_info),
            joinedload(Member.line_info),
            selectinload(Member.tags),
        )
        .order_by(Member.id)
        .all()
    )

    # Build in-memory lookup — avoids re-joining member table in subsequent queries
    members_by_id = {m.id: m for m in all_members}

    all_matchings = (
        session.query(Matching)
        .filter(Matching.status != MatchingStatus.DRAFT)
        .order_by(Matching.id.desc())
        .all()
    )

    draft_matchings = (
        session.query(Matching)
        .filter(Matching.status == MatchingStatus.DRAFT)
        .order_by(Matching.id.asc())
        .all()
    )

    matchings_by_id = {m.id: m for m in all_matchings}

    # Build breakdown lookup for score column popovers
    _pairs = set()
    for m in all_matchings:
        _pairs.add((m.subject_id, m.object_id))
        _pairs.add((m.object_id, m.subject_id))
    breakdowns_by_pair: dict = {}
    if _pairs:
        from sqlalchemy import tuple_
        _score_rows = session.query(UserMatchScore).filter(
            tuple_(UserMatchScore.source_user_id, UserMatchScore.target_user_id).in_(list(_pairs))
        ).all()
        for r in _score_rows:
            breakdowns_by_pair[f"{r.source_user_id}:{r.target_user_id}"] = r.breakdown or {}

    all_proposals = (
        session.query(DateProposal)
        .filter(DateProposal.status != ProposalStatus.DELETED)
        .order_by(DateProposal.proposed_datetime)
        .all()
    )

    all_group_matchings = (
        session.query(GroupMatching)
        .order_by(GroupMatching.id.desc())
        .all()
    )

    member_match_counts = defaultdict(int)
    for m in all_matchings:
        member_match_counts[m.subject_id] += 1
        member_match_counts[m.object_id] += 1

    match_ready_ids = {
        m.id for m in all_members
        if m.line_info and m.introduction_link
    }

    non_eligible = []
    for member in all_members:
        reasons = []
        if not member.is_member_active:
            reasons.append("帳號已停用")
        if member.is_test:
            reasons.append("測試帳號")
        if not member.introduction_link:
            reasons.append("缺少介紹頁連結")
        if not member.line_info:
            reasons.append("未綁定 LINE")
        if member.is_expired:
            reasons.append("會員已到期")
        if member.matching_start_date and member.matching_start_date > date.today():
            reasons.append(f"配對開始日未到（{member.matching_start_date}）")
        if member.matching_end_date and member.matching_end_date < date.today():
            reasons.append(f"配對已結束（{member.matching_end_date}）")
        if reasons:
            non_eligible.append((member, reasons))

    total_users = len(all_members)
    eligible_count = sum(
        1 for m in all_members
        if m.id in match_ready_ids and m.is_member_active and not m.is_test
    )
    active_matchings = sum(
        1 for m in all_matchings if m.status == MatchingStatus.ACTIVE
    )

    confirmed_dates = sum(1 for p in all_proposals if p.status == ProposalStatus.CONFIRMED)
    pending_dates = sum(1 for p in all_proposals if p.status == ProposalStatus.PENDING)

    member_date_counts = defaultdict(int)
    for p in all_proposals:
        if p.status == ProposalStatus.CONFIRMED:
            m = matchings_by_id.get(p.matching_id)
            if m:
                member_date_counts[m.subject_id] += 1
                member_date_counts[m.object_id] += 1

    non_eligible_map = {m.id: reasons for m, reasons in non_eligible}

    # Build per-member match history: { member_id: [(partner_id, cool_name, created_at), ...] }
    member_match_history = defaultdict(list)
    for m in all_matchings:
        member_match_history[m.subject_id].append((m.object_id, m.cool_name, m.created_at))
        member_match_history[m.object_id].append((m.subject_id, m.cool_name, m.created_at))

    # Historical partner ids per member — used in the edit-draft modal to hide
    # candidates that were already paired with the fixed member.
    member_historical_partners: dict[int, list[int]] = {
        mid: [entry[0] for entry in history]
        for mid, history in member_match_history.items()
    }

    # Weeks since each member's last matching (computed from history, not the stored counter)
    _today = date.today()
    weeks_unmatched_by_id: dict = {}
    for m in all_members:
        history = member_match_history.get(m.id, [])
        if not history:
            weeks_unmatched_by_id[m.id] = None
        else:
            latest_dt = max(h[2] for h in history)
            latest_date = latest_dt.date() if hasattr(latest_dt, 'date') else latest_dt
            weeks_unmatched_by_id[m.id] = max(0, (_today - latest_date).days // 7)

    # Build set of previously matched pairs for manual-pair highlight
    matched_pairs_set = set()
    for m in all_matchings:
        matched_pairs_set.add((m.subject_id, m.object_id))
        matched_pairs_set.add((m.object_id, m.subject_id))

    # Build score breakdowns for draft matchings too
    _draft_pairs = set()
    for m in draft_matchings:
        _draft_pairs.add((m.subject_id, m.object_id))
        _draft_pairs.add((m.object_id, m.subject_id))
    if _draft_pairs:
        from sqlalchemy import tuple_
        _draft_score_rows = session.query(UserMatchScore).filter(
            tuple_(UserMatchScore.source_user_id, UserMatchScore.target_user_id).in_(list(_draft_pairs))
        ).all()
        for r in _draft_score_rows:
            breakdowns_by_pair[f"{r.source_user_id}:{r.target_user_id}"] = r.breakdown or {}

    # Lightweight JSONB extract for job — avoids removing the user_info defer.
    from sqlalchemy import text as _sql_text
    _job_rows = session.execute(
        _sql_text("SELECT id, user_info->>'會員之職業類別' FROM member")
    ).all()
    job_by_id = {r[0]: (r[1] or '') for r in _job_rows}

    # Diagnosis (no_candidate_users / unmatched_with_reasons) is deferred to
    # /admin/drafts/diagnosis and loaded via AJAX after the page renders.
    unmatched_with_reasons = []
    no_candidate_users = []

    all_tags = session.query(Tag).order_by(Tag.name).all()

    response = render_template(
        'admin_dashboard.html',
        today=date.today(),
        all_tags=all_tags,
        match_ready_ids=match_ready_ids,
        members_by_id=members_by_id,
        matchings_by_id=matchings_by_id,
        member_match_counts=member_match_counts,
        member_date_counts=member_date_counts,
        non_eligible_map=non_eligible_map,
        members=all_members,
        matchings=all_matchings,
        draft_matchings=draft_matchings,
        non_eligible=non_eligible,
        total_users=total_users,
        eligible_count=eligible_count,
        active_matchings=active_matchings,
        proposals=all_proposals,
        confirmed_dates=confirmed_dates,
        pending_dates=pending_dates,
        breakdowns_by_pair=breakdowns_by_pair,
        member_match_history=member_match_history,
        matched_pairs_set=matched_pairs_set,
        member_historical_partners=member_historical_partners,
        is_dev=settings.is_dev,
        unmatched_with_reasons=unmatched_with_reasons,
        no_candidate_users=no_candidate_users,
        no_candidate_candidates={m.id: candidates for m, _, candidates in unmatched_with_reasons},
        weeks_unmatched_by_id=weeks_unmatched_by_id,
        group_matchings=all_group_matchings,
        job_by_id=job_by_id,
    )
    if cache and not has_flash:
        cache.setex(_DASHBOARD_CACHE_KEY, _DASHBOARD_CACHE_TTL, response)
    return response


@bp.route('/drafts/diagnosis')
@login_required
@admin_required
def drafts_diagnosis():
    """
    Heavy diagnosis block — deferred from the main page load and fetched via
    AJAX so it doesn't block the initial dashboard render.
    """
    session = get_db()

    draft_matchings = session.query(Matching).filter(
        Matching.status == MatchingStatus.DRAFT
    ).all()

    all_matchings = session.query(Matching).filter(
        Matching.status != MatchingStatus.DRAFT
    ).all()

    _today = date.today()
    weeks_unmatched_by_id: dict = {}
    for m in all_matchings:
        dt = m.created_at.date() if hasattr(m.created_at, 'date') else m.created_at
        for uid in (m.subject_id, m.object_id):
            prev = weeks_unmatched_by_id.get(uid)
            if prev is None or dt > prev:
                weeks_unmatched_by_id[uid] = dt
    weeks_unmatched_by_id = {
        uid: max(0, (_today - dt).days // 7)
        for uid, dt in weeks_unmatched_by_id.items()
    }

    eligible_pool = get_eligible_matching_pool(session, defer_user_info=False)

    unmatched_with_reasons = _diagnose_unmatched(
        eligible_pool, draft_matchings, all_matchings, session
    )

    # Users who are overdue (≥1 week unmatched) AND have no mutually compatible
    # candidate at all — combined score > 0 means both directions are positive
    # (neither side has a hard exclude), so any such candidate means the user
    # was simply not reached by the greedy algorithm this cycle, not structurally blocked.
    draft_paired_ids = {uid for m in draft_matchings for uid in (m.subject_id, m.object_id)}
    no_candidate_users = [
        m for m, _, candidates in unmatched_with_reasons
        if m.id not in draft_paired_ids
        and (weeks_unmatched_by_id.get(m.id) is None or weeks_unmatched_by_id.get(m.id) >= 1)
        and not any(score > 0 for _, score in candidates)
    ]
    no_candidate_candidates = {m.id: candidates for m, _, candidates in unmatched_with_reasons}

    return render_template(
        'admin_drafts_diagnosis.html',
        no_candidate_users=no_candidate_users,
        no_candidate_candidates=no_candidate_candidates,
        weeks_unmatched_by_id=weeks_unmatched_by_id,
        draft_count=len(draft_matchings),
        today_year=_today.year,
    )


@bp.route('/users/new', methods=['GET', 'POST'])
@login_required
@admin_required
def new_user():
    if request.method == 'POST':
        session = get_db()

        user_info = {}
        intro_link = request.form.get('introduction_link', '').strip()
        blind_intro_link = request.form.get('blind_introduction_link', '').strip()
        if intro_link:
            user_info['會員介紹頁網址'] = intro_link
        if blind_intro_link:
            user_info['盲約介紹卡一'] = blind_intro_link

        # Matchmaking profile fields → stored in user_info for scoring engine
        _populate_matchmaking_info(user_info, request.form)


        birthday_str = request.form.get('birthday', '').strip()
        birthday = None
        if birthday_str:
            try:
                birthday = datetime.strptime(birthday_str, '%Y-%m-%d').date()
            except ValueError:
                pass

        password_plain = request.form.get('password', '').strip()
        if not password_plain and birthday:
            password_plain = birthday.strftime('%Y%m%d')

        exp_str = request.form.get('expiration_date', '').strip()
        expiration_date = None
        if exp_str:
            try:
                expiration_date = datetime.strptime(exp_str, '%Y-%m-%d').date()
            except ValueError:
                pass

        def _parse_date(key):
            s = request.form.get(key, '').strip()
            if s:
                try:
                    return datetime.strptime(s, '%Y-%m-%d').date()
                except ValueError:
                    pass
            return None

        member = Member(
            name=request.form['name'],
            phone_number=request.form['phone_number'],
            gender=request.form['gender'],
            email=request.form.get('email') or None,
            birthday=birthday,
            height=int(request.form['height']) if request.form.get('height') else None,
            rank=request.form.get('rank') or None,
            marital_status=request.form.get('marital_status') or None,  # also saved to user_info above
            is_member_active='is_active' in request.form,
            is_test='is_test' in request.form,
            is_admin='is_admin' in request.form,
            is_developer='is_developer' in request.form and current_user.is_developer,
            fill_form_at=datetime.now(),
            user_info=user_info,
            introduction_link=intro_link or None,
            expiration_date=expiration_date,
            matching_start_date=_parse_date('matching_start_date'),
            matching_end_date=_parse_date('matching_end_date'),
            pref_min_height=int(request.form['pref_min_height']) if request.form.get('pref_min_height') else None,
            pref_max_height=int(request.form['pref_max_height']) if request.form.get('pref_max_height') else None,
            pref_oldest_birth_year=int(request.form['pref_oldest_birth_year']) if request.form.get('pref_oldest_birth_year') else None,
            pref_youngest_birth_year=int(request.form['pref_youngest_birth_year']) if request.form.get('pref_youngest_birth_year') else None,
            password_hash=hash_password(password_plain) if password_plain else None,  # defaults to birthday if set above
        )
        session.add(member)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            flash(f'手機號碼 {request.form["phone_number"]} 已存在，請使用其他號碼', 'danger')
            return render_template('admin_user_form.html', user=None)
        _invalidate_dashboard_cache()
        flash(f'已新增會員 {member.name}', 'success')
        return redirect(url_for('admin_bp.admin_dashboard'))

    return render_template('admin_user_form.html', user=None)


@bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(user_id):
    session = get_db()
    user = session.get(Member, user_id)
    if user is None:
        flash('找不到該會員', 'danger')
        return redirect(url_for('admin_bp.admin_dashboard'))

    if request.method == 'POST':
        user.name = request.form['name']
        user.gender = request.form['gender']
        user.phone_number = request.form['phone_number']
        user.email = request.form.get('email') or None
        user.rank = request.form.get('rank') or None
        user.marital_status = request.form.get('marital_status') or None
        user.is_member_active = 'is_active' in request.form
        user.is_test = 'is_test' in request.form
        user.is_admin = 'is_admin' in request.form
        if current_user.is_developer:
            user.is_developer = 'is_developer' in request.form

        # Companion score / activity label
        activity_label_val = request.form.get('activity_label', '').strip().upper()
        if activity_label_val:
            try:
                user.activity_label = ActivityLabel[activity_label_val]
            except KeyError:
                pass
        companion_score_str = request.form.get('companion_score', '').strip()
        if companion_score_str.isdigit():
            user.companion_score = int(companion_score_str)
        offense_count_str = request.form.get('observer_offense_count', '').strip()
        if offense_count_str.isdigit():
            user.observer_offense_count = int(offense_count_str)
        if 'reset_observer' in request.form:
            from form_app.services.group_matching import compute_activity_label
            user.activity_label = compute_activity_label(user.companion_score or 0)
            user.observer_since = None
            user.observer_offense_count = 0

        birthday_str = request.form.get('birthday', '').strip()
        if birthday_str:
            try:
                user.birthday = datetime.strptime(birthday_str, '%Y-%m-%d').date()
            except ValueError:
                pass
        else:
            user.birthday = None

        exp_str = request.form.get('expiration_date', '').strip()
        if exp_str:
            try:
                user.expiration_date = datetime.strptime(exp_str, '%Y-%m-%d').date()
            except ValueError:
                pass
        else:
            user.expiration_date = None

        def _parse_date(key):
            s = request.form.get(key, '').strip()
            if s:
                try:
                    return datetime.strptime(s, '%Y-%m-%d').date()
                except ValueError:
                    pass
            return None

        user.matching_start_date = _parse_date('matching_start_date')
        user.matching_end_date = _parse_date('matching_end_date')

        user.height = int(request.form['height']) if request.form.get('height') else None
        user.pref_min_height = int(request.form['pref_min_height']) if request.form.get('pref_min_height') else None
        user.pref_max_height = int(request.form['pref_max_height']) if request.form.get('pref_max_height') else None
        user.pref_oldest_birth_year = int(request.form['pref_oldest_birth_year']) if request.form.get('pref_oldest_birth_year') else None
        user.pref_youngest_birth_year = int(request.form['pref_youngest_birth_year']) if request.form.get('pref_youngest_birth_year') else None

        if user.user_info is None:
            user.user_info = {}
        intro_link = request.form.get('introduction_link', '').strip()
        blind_intro_link = request.form.get('blind_introduction_link', '').strip()
        user.introduction_link = intro_link or None
        user.user_info['會員介紹頁網址'] = intro_link or None
        user.user_info['盲約介紹卡一'] = blind_intro_link or None
        _populate_matchmaking_info(user.user_info, request.form)
        flag_modified(user, 'user_info')

        new_password = request.form.get('password', '').strip()
        if new_password and current_user.is_developer:
            user.password_hash = hash_password(new_password)

        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            flash(f'手機號碼 {request.form["phone_number"]} 已存在，請使用其他號碼', 'danger')
            return render_template('admin_user_form.html', user=user)
        _invalidate_dashboard_cache()
        flash(f'已更新會員 {user.name}', 'success')
        return redirect(url_for('admin_bp.admin_dashboard'))

    from sqlalchemy import or_
    from sqlalchemy.orm import subqueryload
    matchings = (
        session.query(Matching)
        .filter(or_(Matching.subject_id == user_id, Matching.object_id == user_id))
        .options(
            joinedload(Matching.subject),
            joinedload(Matching.object),
            subqueryload(Matching.proposals).joinedload(DateProposal.proposer),
        )
        .order_by(Matching.created_at.desc())
        .all()
    )
    all_tags = session.query(Tag).order_by(Tag.name).all()
    return render_template('admin_user_form.html', user=user, matchings=matchings, all_tags=all_tags)


@bp.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    session = get_db()
    user = session.get(Member, user_id)
    if user is None:
        flash('找不到該會員', 'danger')
        return redirect(url_for('admin_bp.admin_dashboard'))

    if user.all_matches:
        flash(f'無法刪除「{user.name}」：該會員有配對記錄，請先取消所有配對。', 'danger')
        return redirect(url_for('admin_bp.admin_dashboard'))

    if user.group_memberships:
        flash(f'無法刪除「{user.name}」：該會員有群組記錄，請先移除群組。', 'danger')
        return redirect(url_for('admin_bp.admin_dashboard'))

    name = user.name
    try:
        # NULL out nullable FKs that point to this member
        session.query(Invite).filter(Invite.created_by_id == user_id).update(
            {Invite.created_by_id: None}, synchronize_session=False)
        session.query(GroupMembership).filter(GroupMembership.referred_by_id == user_id).update(
            {GroupMembership.referred_by_id: None}, synchronize_session=False)
        session.query(GroupMatching).filter(GroupMatching.opener_member_id == user_id).update(
            {GroupMatching.opener_member_id: None}, synchronize_session=False)
        session.query(GroupMatching).filter(GroupMatching.summary_submitted_by_id == user_id).update(
            {GroupMatching.summary_submitted_by_id: None}, synchronize_session=False)

        # Delete non-nullable dependent rows
        session.query(UserMatchScore).filter(
            (UserMatchScore.source_user_id == user_id) |
            (UserMatchScore.target_user_id == user_id)
        ).delete(synchronize_session=False)
        session.query(Matching).filter(
            ((Matching.subject_id == user_id) | (Matching.object_id == user_id)),
            Matching.status == MatchingStatus.DRAFT,
        ).delete(synchronize_session=False)

        if user.line_info:
            session.delete(user.line_info)

        session.delete(user)
        session.commit()
    except Exception as e:
        session.rollback()
        flash(f'刪除失敗：{e}', 'danger')
        return redirect(url_for('admin_bp.admin_dashboard'))

    _invalidate_dashboard_cache()
    flash(f'已刪除會員「{name}」', 'success')
    return redirect(url_for('admin_bp.admin_dashboard'))


@bp.route('/invites/create', methods=['POST'])
@login_required
@admin_required
def create_invite():
    session = get_db()
    invite = Invite(
        token=str(uuid.uuid4()),
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        created_by_id=current_user.id,
    )
    session.add(invite)
    session.commit()

    link = url_for('profile_bp.register', token=invite.token, _external=True)
    return jsonify({'url': link, 'expires_at': invite.expires_at.strftime('%Y-%m-%d %H:%M UTC')})


@bp.route('/users/<int:user_id>/reset-password', methods=['POST'])
@login_required
@developer_required
def reset_user_password(user_id):
    session = get_db()
    user = session.get(Member, user_id)
    if user is None:
        flash('找不到該會員', 'danger')
        return redirect(url_for('admin_bp.admin_dashboard') + '#actions')

    new_password = request.form.get('new_password', '').strip()
    if len(new_password) < 6:
        flash('新密碼至少需要 6 個字元', 'danger')
        return redirect(url_for('admin_bp.admin_dashboard') + '#actions')

    user.password_hash = hash_password(new_password)
    session.commit()
    _invalidate_dashboard_cache()
    flash(f'已重設「{user.name}」的密碼', 'success')
    return redirect(url_for('admin_bp.admin_dashboard') + '#actions')


@bp.route('/matchings/create-draft-pair', methods=['POST'])
@login_required
@admin_required
def create_draft_pair():
    from sqlalchemy import and_, or_
    session = get_db()

    try:
        subject_id = int(request.form['subject_id'])
        object_id = int(request.form['object_id'])
    except (KeyError, ValueError):
        flash('無效的請求', 'danger')
        return redirect(url_for('admin_bp.admin_dashboard', tab='drafts'))

    subject = session.get(Member, subject_id)
    obj = session.get(Member, object_id)
    if not subject or not obj:
        flash('找不到會員', 'danger')
        return redirect(url_for('admin_bp.admin_dashboard', tab='drafts'))

    if subject.gender == obj.gender:
        flash('不能配對相同性別的會員', 'danger')
        return redirect(url_for('admin_bp.admin_dashboard', tab='drafts'))

    # Only block if either member is already in an active or pending draft matching.
    # CANCELLED / COMPLETED history is allowed to be re-paired.
    existing = session.query(Matching).filter(
        or_(
            and_(Matching.subject_id == subject_id, Matching.object_id == object_id),
            and_(Matching.subject_id == object_id, Matching.object_id == subject_id),
        ),
        Matching.status.in_([MatchingStatus.ACTIVE, MatchingStatus.DRAFT]),
    ).first()
    if existing:
        flash(f'「{subject.name}」與「{obj.name}」已有進行中的配對', 'danger')
        return redirect(url_for('admin_bp.admin_dashboard', tab='drafts'))

    sub_score = session.query(UserMatchScore).filter_by(
        source_user_id=subject_id, target_user_id=object_id
    ).first()
    obj_score = session.query(UserMatchScore).filter_by(
        source_user_id=object_id, target_user_id=subject_id
    ).first()

    new_match = Matching(
        subject_id=subject_id,
        object_id=object_id,
        cool_name=generate_funny_name(),
        grading_metric=int(sub_score.score) if sub_score else 0,
        obj_grading_metric=int(obj_score.score) if obj_score else 0,
        status=MatchingStatus.DRAFT,
        is_match_notified=True,
    )
    session.add(new_match)
    session.commit()
    _invalidate_dashboard_cache()
    flash(f'已新增草稿配對：{subject.name} ＆ {obj.name}', 'success')
    return redirect(url_for('admin_bp.admin_dashboard', tab='drafts'))


@bp.route('/broadcast', methods=['POST'])
@login_required
@admin_required
def broadcast_message():
    session = get_db()
    content = request.form.get('content', '').strip()
    target = request.form.get('target')
    matching_ids = request.form.getlist('matching_ids', type=int)

    if not content:
        flash('訊息內容不能為空', 'danger')
        return redirect(url_for('admin_bp.admin_dashboard', tab='matchings'))

    if target == 'all':
        matchings = session.query(Matching).filter(
            Matching.status == MatchingStatus.ACTIVE
        ).all()
    else:
        if not matching_ids:
            flash('請選擇至少一個配對', 'danger')
            return redirect(url_for('admin_bp.admin_dashboard', tab='matchings'))
        matchings = session.query(Matching).filter(
            Matching.id.in_(matching_ids),
            Matching.status == MatchingStatus.ACTIVE
        ).all()

    if not matchings:
        flash('沒有符合條件的進行中配對', 'warning')
        return redirect(url_for('admin_bp.admin_dashboard', tab='matchings'))

    for matching in matchings:
        msg = Message(
            content=content,
            user_id=matching.subject_id,
            matching_id=matching.id,
            is_system_notification=True,
            is_notified=True,
        )
        session.add(msg)

    involved_ids = {uid for m in matchings for uid in (m.subject_id, m.object_id)}
    members = (
        session.query(Member)
        .filter(Member.id.in_(involved_ids))
        .options(joinedload(Member.line_info))
        .all()
    )
    members_by_id = {m.id: m for m in members}

    session.commit()

    # Deduplicate: collect per-member list of affected matching IDs so a member
    # in multiple targeted matchings receives exactly one LINE push.
    member_matchings: dict[int, list[int]] = defaultdict(list)
    for matching in matchings:
        for uid in (matching.subject_id, matching.object_id):
            member_matchings[uid].append(matching.id)

    from linebot import LineBotApi
    from linebot.models import TextSendMessage
    from form_app.extensions import line_bot_helper

    line_bot_api = LineBotApi(line_bot_helper.configuration.access_token)
    dev = settings.is_dev
    sent = failed = 0

    for uid, mid_list in member_matchings.items():
        member = members_by_id.get(uid)
        if not member:
            continue
        if dev:
            target_line_id = settings.LINE_TEST_USER_ID
        else:
            if not member.line_info:
                continue
            target_line_id = member.line_info.user_id

        if len(mid_list) == 1:
            chat_link = f"🔗 前往對話：{settings.APP_URL}/dashboard/{mid_list[0]}"
        else:
            links = "\n".join(f"  • {settings.APP_URL}/dashboard/{mid}" for mid in mid_list)
            chat_link = f"🔗 受影響的對話：\n{links}"

        line_text = f"📢 系統通知\n\n{content}\n\n{chat_link}"
        try:
            line_bot_api.push_message(target_line_id, TextSendMessage(text=line_text))
            sent += 1
        except Exception as e:
            failed += 1
            print(f"[broadcast] Failed to notify user {uid}: {e}")

    _invalidate_dashboard_cache()
    flash(
        f'廣播訊息已發送至 {len(matchings)} 個配對'
        f'（LINE 通知：{sent} 人成功{"、" + str(failed) + " 人失敗" if failed else ""}）',
        'success'
    )
    return redirect(url_for('admin_bp.admin_dashboard', tab='matchings'))


@bp.route('/matchings/<int:matching_id>/cancel', methods=['POST'])
@login_required
@admin_required
def cancel_matching(matching_id):
    session = get_db()
    matching = session.get(Matching, matching_id)
    if matching is None:
        flash('找不到該配對', 'danger')
        return redirect(url_for('admin_bp.admin_dashboard'))
    matching.cancel(current_user.id)
    session.commit()
    _invalidate_dashboard_cache()
    flash(f'已取消配對「{matching.cool_name}」', 'success')
    back = request.referrer or ''
    if 'matchings' in back and str(matching_id) in back:
        return redirect(url_for('admin_bp.matching_detail', matching_id=matching_id))
    return redirect(url_for('admin_bp.admin_dashboard', tab='matchings'))


@bp.route('/matchings/<int:matching_id>/reactivate', methods=['POST'])
@login_required
@admin_required
def reactivate_matching(matching_id):
    session = get_db()
    matching = session.get(Matching, matching_id)
    if matching is None:
        flash('找不到該配對', 'danger')
        return redirect(url_for('admin_bp.admin_dashboard'))
    matching.activate()
    session.commit()
    _invalidate_dashboard_cache()
    flash(f'已重新啟用配對「{matching.cool_name}」', 'success')
    back = request.referrer or ''
    if 'matchings' in back and str(matching_id) in back:
        return redirect(url_for('admin_bp.matching_detail', matching_id=matching_id))
    return redirect(url_for('admin_bp.admin_dashboard', tab='matchings'))


@bp.route('/groups/create', methods=['POST'])
@login_required
@admin_required
def create_group():
    session = get_db()
    male_ids = request.form.getlist('male_ids', type=int)
    female_ids = request.form.getlist('female_ids', type=int)

    if len(male_ids) != 2 or len(female_ids) != 2:
        flash('請選擇恰好 2 位男性與 2 位女性', 'danger')
        return redirect(url_for('admin_bp.admin_dashboard', tab='groups'))

    all_ids = male_ids + female_ids
    if len(set(all_ids)) != 4:
        flash('不能重複選擇同一位會員', 'danger')
        return redirect(url_for('admin_bp.admin_dashboard', tab='groups'))

    members = session.query(Member).filter(Member.id.in_(all_ids)).all()
    if len(members) != 4:
        flash('找不到部分會員', 'danger')
        return redirect(url_for('admin_bp.admin_dashboard', tab='groups'))

    from form_app.services.cool_name import generate_funny_name
    avatars = assign_session_avatars(len(members))
    group = GroupMatching(
        cool_name=generate_funny_name(),
        expires_at=datetime.now() + timedelta(days=15),
        memberships=[
            GroupMembership(member_id=m.id, session_avatar=avatars[i])
            for i, m in enumerate(members)
        ],
    )
    session.add(group)
    session.commit()
    process_all_notifications(session)
    _invalidate_dashboard_cache()
    flash(f'群組「{group.cool_name}」已建立', 'success')
    return redirect(url_for('admin_bp.admin_dashboard', tab='groups'))


@bp.route('/groups/auto-form', methods=['POST'])
@login_required
@admin_required
def auto_form_groups():
    session = get_db()
    from form_app.services.group_matching import form_groups
    created = form_groups(session)
    session.commit()
    process_all_notifications(session)
    _invalidate_dashboard_cache()
    if created:
        flash(f'自動生成了 {len(created)} 個群組', 'success')
    else:
        flash('目前沒有符合條件的會員可以分組', 'warning')
    return redirect(url_for('admin_bp.admin_dashboard', tab='groups'))


@bp.route('/groups/<int:group_id>/cancel', methods=['POST'])
@login_required
@admin_required
def cancel_group(group_id):
    session = get_db()
    group = session.get(GroupMatching, group_id)
    if group is None:
        flash('找不到該群組', 'danger')
        return redirect(url_for('admin_bp.admin_dashboard', tab='groups'))
    group.status = GroupMatchingStatus.CANCELLED
    session.commit()
    _invalidate_dashboard_cache()
    flash(f'群組「{group.cool_name}」已取消', 'success')
    return redirect(url_for('admin_bp.admin_dashboard', tab='groups'))


def _compute_and_save_score(session, source: Member, target: Member) -> UserMatchScore:
    """Compute a match score between two members and persist it."""
    score, breakdown = calculate_match_score(
        UserProfileAdapter.from_member(source),
        UserProfileAdapter.from_member(target),
    )
    record = UserMatchScore(
        source_user_id=source.id,
        target_user_id=target.id,
        score=score,
        breakdown=breakdown,
    )
    session.add(record)
    return record


@bp.route('/matchings/new', methods=['GET', 'POST'])
@login_required
@admin_required
def new_matching():
    session = get_db()

    if request.method == 'POST':
        subject_id = int(request.form['subject_id'])
        object_id = int(request.form['object_id'])

        if subject_id == object_id:
            flash('不能配對同一個人', 'danger')
            return redirect(url_for('admin_bp.new_matching'))

        sub_member = session.get(Member, subject_id)
        obj_member = session.get(Member, object_id)
        is_test_pair = (sub_member and sub_member.is_test) or (obj_member and obj_member.is_test)

        if not is_test_pair:
            from sqlalchemy import or_ as _or_dup
            existing = session.query(Matching).filter(
                Matching.status != MatchingStatus.DRAFT,
                _or_dup(
                    (Matching.subject_id == subject_id) & (Matching.object_id == object_id),
                    (Matching.subject_id == object_id) & (Matching.object_id == subject_id),
                )
            ).first()
            if existing:
                flash(f'這兩位已有配對紀錄「{existing.cool_name}」，無法重複配對', 'danger')
                return redirect(url_for('admin_bp.new_matching'))

        sub_score = session.query(UserMatchScore).filter(
            UserMatchScore.source_user_id == subject_id,
            UserMatchScore.target_user_id == object_id
        ).first()
        obj_score = session.query(UserMatchScore).filter(
            UserMatchScore.source_user_id == object_id,
            UserMatchScore.target_user_id == subject_id
        ).first()

        if sub_score is None or obj_score is None:
            if sub_score is None:
                sub_score = _compute_and_save_score(session, sub_member, obj_member)
            if obj_score is None:
                obj_score = _compute_and_save_score(session, obj_member, sub_member)

        new_match = Matching(
            subject_id=subject_id,
            object_id=object_id,
            cool_name=generate_funny_name(),
            grading_metric=int(sub_score.score),
            obj_grading_metric=int(obj_score.score),
        )
        session.add(new_match)
        session.flush()
        from form_app.services.messaging import process_all_notifications
        process_all_notifications(session)
        session.commit()
        _invalidate_dashboard_cache()
        flash(f'已手動建立配對「{new_match.cool_name}」', 'success')
        return redirect(url_for('admin_bp.admin_dashboard', tab='matchings'))

    from sqlalchemy import or_ as _or_active
    all_members = (
        session.query(Member)
        .filter(_or_active(Member.is_member_active == True, Member.is_test == True))
        .options(joinedload(Member.line_info))
        .order_by(Member.name)
        .all()
    )
    males = [m for m in all_members if m.gender == 'M']
    females = [m for m in all_members if m.gender == 'F']

    # Build past-match map: { member_id: [partner_id, ...] }
    all_member_ids = [m.id for m in all_members]
    from sqlalchemy import or_ as _or
    past_matchings = session.query(Matching.subject_id, Matching.object_id).filter(
        Matching.status != MatchingStatus.DRAFT,
        _or(
            Matching.subject_id.in_(all_member_ids),
            Matching.object_id.in_(all_member_ids),
        )
    ).all()
    past_partners: dict[int, list[int]] = defaultdict(list)
    for sub, obj in past_matchings:
        past_partners[sub].append(obj)
        past_partners[obj].append(sub)

    return render_template('admin_manual_pair.html', males=males, females=females,
                           past_partners=past_partners)


@bp.route('/send-notifications', methods=['POST'])
@login_required
@admin_required
def send_notifications():
    session = get_db()
    process_all_notifications(session)
    session.commit()
    _invalidate_dashboard_cache()
    flash('已發送所有通知', 'success')
    return redirect(url_for('admin_bp.admin_dashboard', tab='actions'))


@bp.route('/notify-expiring', methods=['POST'])
@login_required
@admin_required
def notify_expiring():
    from dateutil.relativedelta import relativedelta
    from linebot import LineBotApi
    from linebot.models import TextSendMessage
    from sqlalchemy import and_
    from form_app.extensions import line_bot_helper
    from form_app.config import settings

    days_notice = int(request.form.get('days', 7))
    today = date.today()
    cutoff = today + relativedelta(days=days_notice)

    session = get_db()
    expiring = session.query(Member).filter(
        and_(
            Member.is_member_active == True,
            Member.is_test == False,
            Member.expiration_date != None,
            Member.expiration_date >= today,
            Member.expiration_date <= cutoff,
        )
    ).all()

    if not expiring:
        flash(f'沒有在 {days_notice} 天內到期的會員。', 'info')
        return redirect(url_for('admin_bp.admin_dashboard', tab='actions'))

    line_bot_api = LineBotApi(line_bot_helper.configuration.access_token)
    dev = settings.is_dev
    sent = 0

    for member in expiring:
        days_left = (member.expiration_date - today).days
        text = (
            f"親愛的 {member.proper_name}，\n\n"
            f"您的 CityLove 會員資格將於 {member.expiration_date.strftime('%Y/%m/%d')} 到期"
            f"（還有 {days_left} 天）。\n\n"
            f"如需續約，請聯絡我們的客服，謝謝！"
        )
        target = settings.LINE_TEST_USER_ID if dev else (
            member.line_info.user_id if member.line_info else None
        )
        if target:
            line_bot_api.push_message(target, TextSendMessage(text=text))
            sent += 1

    flash(f'已通知 {sent}/{len(expiring)} 位即將到期的會員。', 'success')
    return redirect(url_for('admin_bp.admin_dashboard', tab='actions'))


# ── Draft matching management ────────────────────────────────────────────────

@bp.route('/matchings/<int:matching_id>/edit-draft', methods=['POST'])
@login_required
@admin_required
def edit_draft(matching_id):
    session = get_db()
    matching = session.get(Matching, matching_id)
    if matching is None or not matching.is_draft:
        flash('找不到草稿配對', 'danger')
        return redirect(url_for('admin_bp.admin_dashboard', tab='drafts'))

    new_male_id   = request.form.get('male_id',   type=int)
    new_female_id = request.form.get('female_id', type=int)
    new_cool_name = request.form.get('cool_name', '').strip()

    # Determine current male/female sides
    subj = session.get(Member, matching.subject_id)
    if subj and subj.gender == 'M':
        cur_male_id, cur_female_id = matching.subject_id, matching.object_id
    else:
        cur_male_id, cur_female_id = matching.object_id, matching.subject_id

    final_male_id   = new_male_id   or cur_male_id
    final_female_id = new_female_id or cur_female_id

    if final_male_id == final_female_id:
        flash('男生和女生不能是同一人', 'danger')
        return redirect(url_for('admin_bp.admin_dashboard', tab='drafts'))

    if final_male_id != cur_male_id or final_female_id != cur_female_id:
        from sqlalchemy import or_
        male_member   = session.get(Member, final_male_id)
        female_member = session.get(Member, final_female_id)
        if not male_member or not female_member:
            flash('找不到指定會員', 'danger')
            return redirect(url_for('admin_bp.admin_dashboard', tab='drafts'))

        # Check that the newly assigned members aren't already in another active/draft matching.
        for member, label in ((male_member, '男生'), (female_member, '女生')):
            if member.id in (cur_male_id, cur_female_id):
                continue  # unchanged side — no conflict possible
            conflict = session.query(Matching).filter(
                or_(Matching.subject_id == member.id, Matching.object_id == member.id),
                Matching.status.in_([MatchingStatus.ACTIVE, MatchingStatus.DRAFT]),
                Matching.id != matching_id,
            ).first()
            if conflict:
                flash(f'「{member.name}」已有進行中的配對，無法加入草稿', 'danger')
                return redirect(url_for('admin_bp.admin_dashboard', tab='drafts'))

        score_mf = session.query(UserMatchScore).filter_by(
            source_user_id=final_male_id, target_user_id=final_female_id
        ).first() or _compute_and_save_score(session, male_member, female_member)
        score_fm = session.query(UserMatchScore).filter_by(
            source_user_id=final_female_id, target_user_id=final_male_id
        ).first() or _compute_and_save_score(session, female_member, male_member)

        # Preserve subject=male, object=female convention
        matching.subject_id       = final_male_id
        matching.object_id        = final_female_id
        matching.grading_metric     = int(score_mf.score)
        matching.obj_grading_metric = int(score_fm.score)

    if new_cool_name:
        matching.cool_name = new_cool_name

    session.commit()
    _invalidate_dashboard_cache()
    flash(f'已更新草稿配對「{matching.cool_name}」', 'success')
    return redirect(url_for('admin_bp.admin_dashboard', tab='drafts'))


@bp.route('/matchings/drafts/approve-all', methods=['POST'])
@login_required
@admin_required
def approve_all_drafts():
    session = get_db()
    drafts = session.query(Matching).filter(Matching.status == MatchingStatus.DRAFT).all()
    if not drafts:
        flash('目前沒有草稿配對。', 'info')
        return redirect(url_for('admin_bp.admin_dashboard', tab='drafts'))

    matched_ids = set()
    for m in drafts:
        m.approve_draft()
        matched_ids.add(m.subject_id)
        matched_ids.add(m.object_id)

    # Finalise the cycle: update consecutive_unmatched_weeks now that the
    # draft is committed. This is the correct moment — not during generation,
    # so delete+regenerate doesn't cause spurious increments.
    eligible_pool = get_eligible_matching_pool(session)
    update_unmatched_counters(eligible_pool, matched_ids, session)

    session.commit()
    process_all_notifications(session)
    session.commit()
    _invalidate_dashboard_cache()
    flash(f'已確認 {len(drafts)} 筆配對並發送通知。', 'success')
    return redirect(url_for('admin_bp.admin_dashboard', tab='matchings'))


@bp.route('/matchings/drafts/discard-all', methods=['POST'])
@login_required
@admin_required
def discard_all_drafts():
    session = get_db()
    count = session.query(Matching).filter(Matching.status == MatchingStatus.DRAFT).delete(synchronize_session=False)
    session.commit()
    _invalidate_dashboard_cache()
    flash(f'已刪除 {count} 筆草稿配對。', 'success')
    return redirect(url_for('admin_bp.admin_dashboard', tab='drafts'))


@bp.route('/matchings/<int:matching_id>/approve-draft', methods=['POST'])
@login_required
@admin_required
def approve_draft(matching_id):
    session = get_db()
    matching = session.get(Matching, matching_id)
    if matching is None or not matching.is_draft:
        flash('找不到該草稿配對', 'danger')
        return redirect(url_for('admin_bp.admin_dashboard', tab='drafts'))
    matching.approve_draft()
    # Individual approval counts as a partial finalisation for these two members only
    eligible_pool = get_eligible_matching_pool(session)
    update_unmatched_counters(eligible_pool, {matching.subject_id, matching.object_id}, session)
    session.commit()
    process_all_notifications(session)
    session.commit()
    _invalidate_dashboard_cache()
    flash(f'已確認配對「{matching.cool_name}」並發送通知。', 'success')
    return redirect(url_for('admin_bp.admin_dashboard', tab='drafts'))


@bp.route('/matchings/<int:matching_id>/delete-draft', methods=['POST'])
@login_required
@admin_required
def delete_draft(matching_id):
    session = get_db()
    matching = session.get(Matching, matching_id)
    if matching is None or not matching.is_draft:
        flash('找不到該草稿配對', 'danger')
        return redirect(url_for('admin_bp.admin_dashboard', tab='drafts'))
    cool_name = matching.cool_name
    session.delete(matching)
    session.commit()
    _invalidate_dashboard_cache()
    flash(f'已刪除草稿配對「{cool_name}」。', 'success')
    return redirect(url_for('admin_bp.admin_dashboard', tab='drafts'))


@bp.route('/matchings/<int:matching_id>', methods=['GET'])
@login_required
@admin_required
def matching_detail(matching_id):
    from sqlalchemy import tuple_
    from sqlalchemy.orm import subqueryload
    session = get_db()
    matching = (
        session.query(Matching)
        .filter(Matching.id == matching_id)
        .options(
            joinedload(Matching.subject),
            joinedload(Matching.object),
            subqueryload(Matching.proposals).joinedload(DateProposal.proposer),
            subqueryload(Matching.messages).joinedload(Message.user),
        )
        .first()
    )
    if matching is None:
        flash('找不到該配對', 'danger')
        return redirect(url_for('admin_bp.admin_dashboard', tab='matchings'))

    # Score breakdowns for both directions
    score_rows = session.query(UserMatchScore).filter(
        tuple_(UserMatchScore.source_user_id, UserMatchScore.target_user_id).in_([
            (matching.subject_id, matching.object_id),
            (matching.object_id, matching.subject_id),
        ])
    ).all()
    breakdown_subj = next(
        (r.breakdown or {} for r in score_rows if r.source_user_id == matching.subject_id), {}
    )
    breakdown_obj = next(
        (r.breakdown or {} for r in score_rows if r.source_user_id == matching.object_id), {}
    )

    proposals = sorted(matching.proposals, key=lambda p: p.proposed_datetime)
    messages = sorted(matching.messages, key=lambda m: m.timestamp)

    return render_template(
        'admin_matching_detail.html',
        matching=matching,
        breakdown_subj=breakdown_subj,
        breakdown_obj=breakdown_obj,
        proposals=proposals,
        messages=messages,
    )


@bp.route('/matchings/<int:matching_id>/edit-cool-name', methods=['POST'])
@login_required
@admin_required
def matching_edit_cool_name(matching_id):
    session = get_db()
    matching = session.get(Matching, matching_id)
    if matching is None:
        flash('找不到該配對', 'danger')
        return redirect(url_for('admin_bp.admin_dashboard', tab='matchings'))
    matching.cool_name = request.form.get('cool_name', '').strip() or matching.cool_name
    session.commit()
    _invalidate_dashboard_cache()
    flash('已更新代號', 'success')
    return redirect(url_for('admin_bp.matching_detail', matching_id=matching_id))


@bp.route('/matchings/<int:matching_id>/complete', methods=['POST'])
@login_required
@admin_required
def complete_matching(matching_id):
    session = get_db()
    matching = session.get(Matching, matching_id)
    if matching is None:
        flash('找不到該配對', 'danger')
        return redirect(url_for('admin_bp.admin_dashboard', tab='matchings'))
    matching.complete()
    session.commit()
    _invalidate_dashboard_cache()
    flash(f'已將配對「{matching.cool_name}」標記為已完成', 'success')
    return redirect(url_for('admin_bp.matching_detail', matching_id=matching_id))


@bp.route('/matchings/<int:matching_id>/resend-notification', methods=['POST'])
@login_required
@admin_required
def matching_resend_notification(matching_id):
    session = get_db()
    matching = session.get(Matching, matching_id)
    if matching is None:
        flash('找不到該配對', 'danger')
        return redirect(url_for('admin_bp.admin_dashboard', tab='matchings'))
    matching.is_match_notified = False
    session.commit()
    process_all_notifications(session)
    flash('已重新發送配對通知', 'success')
    return redirect(url_for('admin_bp.matching_detail', matching_id=matching_id))


@bp.route('/matchings/<int:matching_id>/proposals/<int:proposal_id>/confirm', methods=['POST'])
@login_required
@admin_required
def matching_confirm_proposal(matching_id, proposal_id):
    session = get_db()
    proposal = session.get(DateProposal, proposal_id)
    if proposal is None or proposal.matching_id != matching_id:
        flash('找不到該提案', 'danger')
        return redirect(url_for('admin_bp.matching_detail', matching_id=matching_id))
    proposal.confirm()
    session.commit()
    flash('已確認見面提案', 'success')
    return redirect(url_for('admin_bp.matching_detail', matching_id=matching_id))


@bp.route('/matchings/<int:matching_id>/proposals/<int:proposal_id>/delete', methods=['POST'])
@login_required
@admin_required
def matching_delete_proposal(matching_id, proposal_id):
    session = get_db()
    proposal = session.get(DateProposal, proposal_id)
    if proposal is None or proposal.matching_id != matching_id:
        flash('找不到該提案', 'danger')
        return redirect(url_for('admin_bp.matching_detail', matching_id=matching_id))
    proposal.delete()
    session.commit()
    flash('已刪除見面提案', 'success')
    return redirect(url_for('admin_bp.matching_detail', matching_id=matching_id))


@bp.route('/members/<int:user_id>/match-history')
@login_required
@admin_required
def member_match_history(user_id):
    """Returns JSON with the matching history for a member (for modal display)."""
    from flask import jsonify
    from sqlalchemy import or_
    session = get_db()
    member = session.get(Member, user_id)
    if member is None:
        return jsonify({'error': '找不到會員'}), 404
    matchings = session.query(Matching).filter(
        Matching.status != MatchingStatus.DRAFT,
        or_(Matching.subject_id == user_id, Matching.object_id == user_id)
    ).order_by(Matching.created_at.desc()).all()
    history = []
    for m in matchings:
        partner_id = m.object_id if m.subject_id == user_id else m.subject_id
        partner = session.get(Member, partner_id)
        history.append({
            'cool_name': m.cool_name,
            'partner_name': partner.name if partner else '—',
            'partner_id': partner_id,
            'status': m.status.value,
            'created_at': m.created_at.strftime('%Y-%m-%d'),
        })
    return jsonify({'member_name': member.name, 'history': history})


@bp.route('/leads')
@login_required
@admin_required
def leads_list():
    session = get_db()
    status_filter = request.args.get('status', 'PENDING')
    try:
        status_enum = LeadSubmissionStatus[status_filter]
    except KeyError:
        status_enum = LeadSubmissionStatus.PENDING
    leads = (
        session.query(LeadSubmission)
        .filter_by(status=status_enum)
        .order_by(LeadSubmission.submitted_at.desc())
        .all()
    )
    pending_count = session.query(LeadSubmission).filter_by(status=LeadSubmissionStatus.PENDING).count()
    return render_template('admin_leads.html', leads=leads, status_filter=status_filter, pending_count=pending_count)


@bp.route('/leads/<int:lead_id>/approve', methods=['POST'])
@login_required
@admin_required
def approve_lead(lead_id):
    session = get_db()
    lead = session.get(LeadSubmission, lead_id)
    if not lead or lead.status != LeadSubmissionStatus.PENDING:
        flash('名單已處理或不存在', 'warning')
        return redirect(url_for('admin_bp.leads_list'))

    existing = session.query(Member).filter_by(phone_number=lead.phone_number).first()
    if existing:
        flash(f'手機 {lead.phone_number} 已是會員 #{existing.id} {existing.name}', 'danger')
        return redirect(url_for('admin_bp.leads_list'))

    member = Member(
        name=lead.name or '待補充',
        phone_number=lead.phone_number,
        gender=lead.gender or 'F',
        fill_form_at=lead.submitted_at,
        is_member_active=False,
        user_info={},
        join_campaign='meta_lead',
    )
    session.add(member)
    session.flush()

    lead.status = LeadSubmissionStatus.APPROVED
    lead.converted_member_id = member.id

    try:
        session.commit()
        flash(f'已建立會員 #{member.id}，請補充詳細資料後再啟用', 'success')
        return redirect(url_for('admin_bp.edit_user', user_id=member.id))
    except Exception as e:
        session.rollback()
        flash(f'建立失敗：{e}', 'danger')
        return redirect(url_for('admin_bp.leads_list'))


@bp.route('/leads/<int:lead_id>/reject', methods=['POST'])
@login_required
@admin_required
def reject_lead(lead_id):
    session = get_db()
    lead = session.get(LeadSubmission, lead_id)
    if lead and lead.status == LeadSubmissionStatus.PENDING:
        lead.status = LeadSubmissionStatus.REJECTED
        session.commit()
        flash('已拒絕名單', 'info')
    return redirect(url_for('admin_bp.leads_list'))


# ── Tag management ─────────────────────────────────────────────────────────

TAG_COLORS = ['primary', 'secondary', 'success', 'danger', 'warning', 'info', 'dark']


@bp.route('/tags', methods=['GET'])
@login_required
@admin_required
def list_tags():
    session = get_db()
    tags = session.query(Tag).order_by(Tag.name).all()
    return jsonify([{'id': t.id, 'name': t.name, 'color': t.color} for t in tags])


@bp.route('/tags', methods=['POST'])
@login_required
@admin_required
def create_tag():
    session = get_db()
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    color = data.get('color', 'secondary')
    if not name:
        return jsonify({'error': '標籤名稱不能為空'}), 400
    if color not in TAG_COLORS:
        color = 'secondary'
    if session.query(Tag).filter_by(name=name).first():
        return jsonify({'error': '標籤名稱已存在'}), 409
    tag = Tag(name=name, color=color, created_by_id=current_user.id)
    session.add(tag)
    session.commit()
    _invalidate_dashboard_cache()
    return jsonify({'id': tag.id, 'name': tag.name, 'color': tag.color}), 201


@bp.route('/tags/<int:tag_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_tag(tag_id):
    session = get_db()
    tag = session.get(Tag, tag_id)
    if not tag:
        return jsonify({'error': '找不到標籤'}), 404
    session.delete(tag)
    session.commit()
    _invalidate_dashboard_cache()
    return jsonify({'ok': True})


@bp.route('/members/<int:user_id>/tags', methods=['POST'])
@login_required
@admin_required
def add_member_tag(user_id):
    session = get_db()
    member = session.query(Member).options(selectinload(Member.tags)).get(user_id)
    data = request.get_json() or {}
    tag = session.get(Tag, data.get('tag_id'))
    if not member or not tag:
        return jsonify({'error': '找不到會員或標籤'}), 404
    if tag not in member.tags:
        member.tags.append(tag)
        session.commit()
    _invalidate_dashboard_cache()
    return jsonify({'ok': True})


@bp.route('/members/<int:user_id>/tags/<int:tag_id>', methods=['DELETE'])
@login_required
@admin_required
def remove_member_tag(user_id, tag_id):
    session = get_db()
    member = session.query(Member).options(selectinload(Member.tags)).get(user_id)
    tag = session.get(Tag, tag_id)
    if not member or not tag:
        return jsonify({'error': '找不到會員或標籤'}), 404
    if tag in member.tags:
        member.tags.remove(tag)
        session.commit()
    _invalidate_dashboard_cache()
    return jsonify({'ok': True})
