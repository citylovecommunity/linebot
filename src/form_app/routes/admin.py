import threading
import time as _time
from datetime import datetime, date

from flask import Blueprint, render_template, redirect, url_for, flash, request, session as flask_session
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload, defer
from sqlalchemy.orm.attributes import flag_modified

# ── Admin dashboard cache ──────────────────────────────────────────────────────
# The dashboard queries are expensive (remote Neon DB in Singapore).
# Cache the rendered HTML for 60s. The cache is bypassed automatically when
# Flask has pending flash messages, which means the admin just performed an
# action and needs to see fresh data.
_dashboard_cache: dict = {'html': None, 'expires': 0.0}
_dashboard_cache_lock = threading.Lock()
_DASHBOARD_CACHE_TTL = 60  # seconds


def _invalidate_dashboard_cache():
    with _dashboard_cache_lock:
        _dashboard_cache['expires'] = 0.0

from form_app.models import Member, Matching, MatchingStatus, UserMatchScore, DateProposal, ProposalStatus, Line_Info
from collections import defaultdict
from form_app.decorators import admin_required
from form_app.database import get_db
from form_app.services.cool_name import generate_funny_name
from form_app.services.messaging import process_all_notifications
from form_app.services.scoring import UserProfileAdapter, calculate_match_score
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


@bp.route('/dashboard')
@login_required
@admin_required
def admin_dashboard():
    # Serve cached HTML if available and no pending flash messages
    has_flash = bool(flask_session.get('_flashes'))
    now = _time.time()
    if not has_flash:
        with _dashboard_cache_lock:
            if _dashboard_cache['html'] and now < _dashboard_cache['expires']:
                return _dashboard_cache['html']

    session = get_db()

    all_members = (
        session.query(Member)
        .options(
            defer(Member.user_info),
            joinedload(Member.line_info),
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
        if not member.is_active:
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
        if m.id in match_ready_ids and m.is_active and not m.is_test
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

    response = render_template(
        'admin_dashboard.html',
        today=date.today(),
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
        is_dev=settings.is_dev,
    )
    with _dashboard_cache_lock:
        _dashboard_cache['html'] = response
        _dashboard_cache['expires'] = _time.time() + _DASHBOARD_CACHE_TTL
    return response


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
            is_active='is_active' in request.form,
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
        session.commit()
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
        user.is_active = 'is_active' in request.form
        user.is_test = 'is_test' in request.form
        user.is_admin = 'is_admin' in request.form
        if current_user.is_developer:
            user.is_developer = 'is_developer' in request.form

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

        session.commit()
        _invalidate_dashboard_cache()
        flash(f'已更新會員 {user.name}', 'success')
        return redirect(url_for('admin_bp.admin_dashboard'))

    return render_template('admin_user_form.html', user=user)


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

    # Remove related scores and line_info before deleting member
    session.query(UserMatchScore).filter(
        (UserMatchScore.source_user_id == user_id) |
        (UserMatchScore.target_user_id == user_id)
    ).delete(synchronize_session=False)
    if user.line_info:
        session.delete(user.line_info)

    name = user.name
    session.delete(user)
    session.commit()
    _invalidate_dashboard_cache()
    flash(f'已刪除會員「{name}」', 'success')
    return redirect(url_for('admin_bp.admin_dashboard'))


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
    return redirect(url_for('admin_bp.admin_dashboard', tab='matchings'))


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

        sub_score = session.query(UserMatchScore).filter(
            UserMatchScore.source_user_id == subject_id,
            UserMatchScore.target_user_id == object_id
        ).first()
        obj_score = session.query(UserMatchScore).filter(
            UserMatchScore.source_user_id == object_id,
            UserMatchScore.target_user_id == subject_id
        ).first()

        if sub_score is None or obj_score is None:
            subject_member = session.get(Member, subject_id)
            object_member = session.get(Member, object_id)
            if sub_score is None:
                sub_score = _compute_and_save_score(session, subject_member, object_member)
            if obj_score is None:
                obj_score = _compute_and_save_score(session, object_member, subject_member)

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

    all_members = (
        session.query(Member)
        .filter(Member.is_active == True)
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
            Member.is_active == True,
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
        male_member   = session.get(Member, final_male_id)
        female_member = session.get(Member, final_female_id)
        if not male_member or not female_member:
            flash('找不到指定會員', 'danger')
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
    for m in drafts:
        m.approve_draft()
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
