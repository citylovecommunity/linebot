from datetime import datetime, date

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload, subqueryload, defer
from sqlalchemy.orm.attributes import flag_modified

from form_app.models import Member, Matching, MatchingStatus, UserMatchScore, DateProposal, ProposalStatus
from form_app.decorators import admin_required
from form_app.database import get_db
from form_app.services.cool_name import generate_funny_name
from form_app.services.messaging import process_all_notifications
from form_app.services.scoring import UserProfileAdapter, calculate_match_score
from form_app.services.security import hash_password


bp = Blueprint('admin_bp', __name__, url_prefix='/admin')


@bp.route('/dashboard')
@login_required
@admin_required
def admin_dashboard():
    session = get_db()
    all_members = (
        session.query(Member)
        .options(
            defer(Member.unread_count),
            joinedload(Member.line_info),
            subqueryload(Member.matches_as_subject),
            subqueryload(Member.matches_as_object),
        )
        .order_by(Member.id)
        .all()
    )
    all_matchings = (
        session.query(Matching)
        .options(
            joinedload(Matching.subject),
            joinedload(Matching.object),
        )
        .order_by(Matching.id.desc())
        .all()
    )

    all_proposals = (
        session.query(DateProposal)
        .filter(DateProposal.status != ProposalStatus.DELETED)
        .options(
            joinedload(DateProposal.matching).joinedload(Matching.subject),
            joinedload(DateProposal.matching).joinedload(Matching.object),
            joinedload(DateProposal.proposer),
        )
        .order_by(DateProposal.proposed_datetime)
        .all()
    )

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
        if reasons:
            non_eligible.append((member, reasons))

    total_users = len(all_members)
    eligible_count = sum(
        1 for m in all_members
        if m.is_match_ready and m.is_active and not m.is_test
    )
    active_matchings = sum(
        1 for m in all_matchings if m.status == MatchingStatus.ACTIVE
    )

    confirmed_dates = sum(1 for p in all_proposals if p.status == ProposalStatus.CONFIRMED)
    pending_dates = sum(1 for p in all_proposals if p.status == ProposalStatus.PENDING)

    from collections import defaultdict
    member_date_counts = defaultdict(int)
    for p in all_proposals:
        if p.status == ProposalStatus.CONFIRMED:
            member_date_counts[p.matching.subject_id] += 1
            member_date_counts[p.matching.object_id] += 1

    non_eligible_map = {m.id: reasons for m, reasons in non_eligible}

    return render_template(
        'admin_dashboard.html',
        today=date.today(),
        member_date_counts=member_date_counts,
        non_eligible_map=non_eligible_map,
        members=all_members,
        matchings=all_matchings,
        non_eligible=non_eligible,
        total_users=total_users,
        eligible_count=eligible_count,
        active_matchings=active_matchings,
        proposals=all_proposals,
        confirmed_dates=confirmed_dates,
        pending_dates=pending_dates,
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

        member = Member(
            name=request.form['name'],
            phone_number=request.form['phone_number'],
            gender=request.form['gender'],
            email=request.form.get('email') or None,
            birthday=birthday,
            height=int(request.form['height']) if request.form.get('height') else None,
            rank=request.form.get('rank') or None,
            marital_status=request.form.get('marital_status') or None,
            is_active='is_active' in request.form,
            is_test='is_test' in request.form,
            fill_form_at=datetime.now(),
            user_info=user_info,
            expiration_date=expiration_date,
            pref_min_height=int(request.form['pref_min_height']) if request.form.get('pref_min_height') else None,
            pref_max_height=int(request.form['pref_max_height']) if request.form.get('pref_max_height') else None,
            pref_oldest_birth_year=int(request.form['pref_oldest_birth_year']) if request.form.get('pref_oldest_birth_year') else None,
            pref_youngest_birth_year=int(request.form['pref_youngest_birth_year']) if request.form.get('pref_youngest_birth_year') else None,
            password_hash=hash_password(password_plain) if password_plain else None,  # defaults to birthday if set above
        )
        session.add(member)
        session.commit()
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

        user.height = int(request.form['height']) if request.form.get('height') else None
        user.pref_min_height = int(request.form['pref_min_height']) if request.form.get('pref_min_height') else None
        user.pref_max_height = int(request.form['pref_max_height']) if request.form.get('pref_max_height') else None
        user.pref_oldest_birth_year = int(request.form['pref_oldest_birth_year']) if request.form.get('pref_oldest_birth_year') else None
        user.pref_youngest_birth_year = int(request.form['pref_youngest_birth_year']) if request.form.get('pref_youngest_birth_year') else None

        if user.user_info is None:
            user.user_info = {}
        intro_link = request.form.get('introduction_link', '').strip()
        blind_intro_link = request.form.get('blind_introduction_link', '').strip()
        user.user_info['會員介紹頁網址'] = intro_link or None
        user.user_info['盲約介紹卡一'] = blind_intro_link or None
        flag_modified(user, 'user_info')

        session.commit()
        flash(f'已更新會員 {user.name}', 'success')
        return redirect(url_for('admin_bp.admin_dashboard'))

    return render_template('admin_user_form.html', user=user)


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
    flash(f'已重新啟用配對「{matching.cool_name}」', 'success')
    return redirect(url_for('admin_bp.admin_dashboard', tab='matchings'))


def _compute_and_save_score(session, source: Member, target: Member) -> UserMatchScore:
    """Compute a match score between two members and persist it."""
    score, breakdown = calculate_match_score(
        UserProfileAdapter(source.user_info or {}),
        UserProfileAdapter(target.user_info or {}),
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
        session.commit()
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
    return render_template('admin_manual_pair.html', males=males, females=females)


@bp.route('/send-notifications', methods=['POST'])
@login_required
@admin_required
def send_notifications():
    session = get_db()
    process_all_notifications(session)
    session.commit()
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
