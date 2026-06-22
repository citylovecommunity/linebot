
from typing import Optional

from flask import (Blueprint, abort, flash, jsonify, redirect, render_template,
                   request, url_for)
from flask_login import current_user, login_required

from form_app.database import get_db
from form_app.models import (
    ActivityLabel, BadgeType, DateProposal, GroupBadge, Matching, Member, Message,
    GroupMatching, GroupMembership, GroupMessage, GroupDateProposal,
)
from form_app.services.security import verify_password, hash_password
from form_app.services.liff_token import make_liff_token
from form_app.config import settings

bp = Blueprint('dashboard_bp', __name__, url_prefix="/dashboard")


def get_matching_or_abort(matching_id) -> Matching:
    """
    Fetches a matching by ID and enforces:
    1. 404 if not found
    2. 403 if current_user is not a participant
    """
    db = get_db()
    matching = db.query(Matching).get(matching_id)

    # 1. Check Existence
    if not matching:
        return None

    is_participant = (
        current_user.id == matching.subject_id or
        current_user.id == matching.object_id
    )

    if not is_participant:

        return None

    return matching


@bp.route('/debug-user')
def debug_user():
    if not settings.is_dev:
        abort(404)

    return {
        "is_authenticated": current_user.is_authenticated,
        "is_anonymous": current_user.is_anonymous,
        "is_active": current_user.is_member_active if hasattr(current_user, 'is_member_active') else "N/A",
        "user_id": current_user.get_id() if hasattr(current_user, 'get_id') else "N/A",
    }


@bp.route('/')
@login_required
def dashboard():
    missing_items = current_user.missing_requirements
    db = get_db()
    group_matchings = (
        db.query(GroupMatching)
        .filter(GroupMatching.memberships.any(GroupMembership.member_id == current_user.id))
        .order_by(GroupMatching.id.desc())
        .all()
    )

    from form_app.services.match_intro import generate_match_intro
    match_intros = {
        m.id: generate_match_intro(current_user, m.get_partner(current_user.id))
        for m in current_user.all_matches
    }

    return render_template('dashboard.html',
                           current_user=current_user,
                           missing_items=missing_items,
                           group_matchings=group_matchings,
                           match_intros=match_intros)


@bp.route('/<int:matching_id>', methods=['GET', 'POST'])
@login_required
def matching_detail(matching_id):
    matching = get_matching_or_abort(matching_id)
    if matching is None:
        flash("matching錯誤", "danger")
        return redirect(url_for('dashboard_bp.dashboard'))

    # 新增訊息已讀
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    for msg in matching.messages:
        if msg.read_at is None and msg.receiver_id == current_user.id:
            msg.read_at = now

    current_user.last_seen_at = now

    db = get_db()
    db.commit()

    partner = matching.get_partner(current_user.id)
    proposal = matching.ui_proposal
    messages = matching.messages

    from form_app.services.match_intro import generate_match_intro
    match_intro = generate_match_intro(current_user, partner)

    status_step = 1
    if proposal:
        if proposal.is_pending:
            status_step = 2
        elif proposal.is_confirmed:
            status_step = 3
        elif proposal.is_cancelled:
            status_step = 4

    return render_template('matching_dashboard.html',
                           matching=matching,
                           status_step=status_step,
                           current_user=current_user,
                           partner=partner,
                           proposal=proposal,
                           messages=messages,
                           match_intro=match_intro,
                           is_dev=settings.is_dev,
                           )


@bp.route('/submit_message/<int:matching_id>', methods=['POST'])
@login_required
def submit_message(matching_id):
    db = get_db()
    matching = get_matching_or_abort(matching_id)
    content = request.form.get('message_content') or (request.json or {}).get('content', '')
    if not content:
        if request.is_json:
            return jsonify({'error': 'empty message'}), 400
        return redirect(request.referrer)

    new_msg = Message(
        content=content,
        user_id=current_user.id,
        matching=matching
    )
    db.add(new_msg)
    db.flush()

    matching.last_message_id = new_msg.id
    db.commit()

    if request.is_json:
        return jsonify({
            'id': new_msg.id,
            'content': new_msg.content,
            'is_me': True,
            'sender_name': current_user.proper_name,
            'timestamp': new_msg.timestamp.strftime('%Y-%m-%d %H:%M'),
            'is_system_notification': False,
        })
    return redirect(request.referrer)


@bp.route('/messages/<int:matching_id>', methods=['GET'])
@login_required
def get_messages(matching_id):
    """Return messages after a given message id for live chat polling."""
    matching = get_matching_or_abort(matching_id)
    after_id = request.args.get('after_id', 0, type=int)
    db = get_db()
    msgs = (
        db.query(Message)
        .filter(Message.matching_id == matching_id, Message.id > after_id)
        .order_by(Message.id)
        .all()
    )
    return jsonify([{
        'id': m.id,
        'content': m.content,
        'is_me': m.user_id == current_user.id,
        'sender_name': m.user.proper_name,
        'timestamp': m.timestamp.strftime('%Y-%m-%d %H:%M'),
        'is_system_notification': m.is_system_notification,
    } for m in msgs])


@bp.route('/submit_proposal/<int:matching_id>', methods=['POST'])
@login_required
def submit_proposal(matching_id):
    db = get_db()
    matching = get_matching_or_abort(matching_id)
    # 1. Validation logic
    restaurant = request.form.get('restaurant')
    date_str = request.form.get('date_time')

    if not restaurant or not date_str:
        flash("Please fill in all fields!", "danger")
        return redirect(url_for('.matching_detail', matching_id=matching_id))

    # 必須先把之前的取消掉
    if matching.ui_proposal:
        matching.ui_proposal.delete()

    # 2. Save to DB (using the ORM strategy we discussed)
    from datetime import datetime
    new_proposal = DateProposal(
        matching_id=matching_id,
        proposer_id=current_user.id,
        restaurant_name=restaurant,
        proposed_datetime=datetime.strptime(
            date_str, '%Y-%m-%dT%H:%M'),  # adjust format
        booker_role=request.form.get('booker')
    )
    db.add(new_proposal)
    db.commit()

    # 3. Notify and Redirect
    flash("Proposal sent successfully!", "success")
    return redirect(url_for('.matching_detail', matching_id=matching_id))


@bp.route('/update_match_status/<int:matching_id>', methods=['POST'])
@login_required
def update_match_status(matching_id):
    db = get_db()
    matching = get_matching_or_abort(matching_id)

    action = request.form.get('action')
    if action == 'active':
        matching.activate()
        flash("Matching Activated!", "success")
    elif action == 'cancelled':
        matching.cancel(current_user.id)
        flash("Matching Cancelled!", "success")
    db.commit()

    return redirect(url_for('.matching_detail', matching_id=matching_id))


@bp.route('/handle_proposal/<int:matching_id>/<int:proposal_id>', methods=['POST'])
@login_required
def handle_proposal(matching_id, proposal_id):
    # 1. Fetch the Match and Proposal
    db = get_db()
    matching = get_matching_or_abort(matching_id)

    action = request.form.get('action')  # 'accept' or 'reject'
    proposal: Optional[DateProposal] = db.query(DateProposal).get(proposal_id)

    # 3. Handle "ACCEPT"
    if action == 'accept':

        # D. Create System Message (So it shows in chat)
        sys_msg = Message(
            matching=matching,
            user_id=current_user.id,  # Attributed to the acceptor
            content=f"✅ 接受在{proposal.restaurant_name}的約會提議!",
            is_system_notification=True
        )

        proposal.confirm()
        db.add(sys_msg)

        flash("Date confirmed!", "success")

    # 4. Handle "REJECT"
    elif action == 'reject':
        # A. Create System Message
        sys_msg = Message(
            matching=matching,
            user_id=current_user.id,
            content=f"❌ {proposal.restaurant_name}提議已取消",
            is_system_notification=True
        )
        proposal.delete()

        db.add(sys_msg)
        flash("Proposal declined.", "info")

    db.commit()

    return redirect(url_for('.matching_detail', matching_id=matching_id))


def _get_group_and_membership(group_id):
    """Returns (group, my_membership) or (None, None) if not found / not a member."""
    db = get_db()
    group = db.get(GroupMatching, group_id)
    if not group:
        return None, None
    membership = db.query(GroupMembership).filter_by(
        group_id=group_id, member_id=current_user.id
    ).first()
    if not membership:
        return None, None
    return group, membership


# Keep old name as alias so existing callers inside this file still work
def get_group_or_abort(group_id):
    group, _ = _get_group_and_membership(group_id)
    return group


@bp.route('/group/<int:group_id>', methods=['GET'])
@login_required
def group_detail(group_id):
    group, my_membership = _get_group_and_membership(group_id)
    if group is None:
        flash('群組不存在或您不是成員', 'danger')
        return redirect(url_for('dashboard_bp.dashboard'))

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    current_user.last_seen_at = now
    db = get_db()
    db.commit()

    memberships_by_id = {m.member_id: m for m in group.memberships}
    days_remaining = None
    if group.expires_at:
        delta = group.expires_at - datetime.now()
        days_remaining = max(0, delta.days)

    # Has the current user already submitted badges this session?
    badge_submitted = db.query(GroupBadge).filter_by(
        group_id=group_id, from_member_id=current_user.id
    ).first() is not None

    # For closed/feedback groups: count received positive badges per member (anonymous)
    received_badges: dict[int, dict[str, int]] = {}
    if group.is_closed or group.is_feedback:
        all_badges = db.query(GroupBadge).filter_by(group_id=group_id).all()
        for badge in all_badges:
            if badge.badge_type == BadgeType.NO_SHOW:
                continue
            bucket = received_badges.setdefault(badge.to_member_id, {})
            key = badge.badge_type.value
            bucket[key] = bucket.get(key, 0) + 1

    return render_template('group_chat.html',
                           group=group,
                           my_membership=my_membership,
                           memberships_by_id=memberships_by_id,
                           messages=group.messages,
                           days_remaining=days_remaining,
                           badge_submitted=badge_submitted,
                           received_badges=received_badges,
                           current_user=current_user,
                           is_dev=settings.is_dev)


@bp.route('/group/<int:group_id>/send', methods=['POST'])
@login_required
def group_send_message(group_id):
    db = get_db()
    group, my_membership = _get_group_and_membership(group_id)
    if group is None:
        return jsonify({'error': 'forbidden'}), 403
    if not group.is_active:
        return jsonify({'error': 'group not active'}), 400

    content = (request.json or {}).get('content', '') or request.form.get('message_content', '')
    if not content:
        return jsonify({'error': 'empty message'}), 400

    msg = GroupMessage(content=content, sender_id=current_user.id, group_id=group.id)
    db.add(msg)
    db.flush()
    group.last_message_id = msg.id

    if my_membership:
        my_membership.message_count += 1

    db.commit()

    return jsonify({
        'id': msg.id,
        'content': msg.content,
        'is_me': True,
        'sender_name': current_user.proper_name,
        'sender_avatar': my_membership.session_avatar if my_membership else '',
        'timestamp': msg.timestamp.strftime('%Y-%m-%d %H:%M'),
        'is_system_notification': False,
    })


@bp.route('/group/<int:group_id>/messages', methods=['GET'])
@login_required
def group_get_messages(group_id):
    group = get_group_or_abort(group_id)
    if group is None:
        return jsonify([]), 403

    after_id = request.args.get('after_id', 0, type=int)
    db = get_db()
    msgs = (
        db.query(GroupMessage)
        .filter(GroupMessage.group_id == group_id, GroupMessage.id > after_id)
        .order_by(GroupMessage.id)
        .all()
    )
    memberships_by_id = {gm.member_id: gm for gm in group.memberships}

    def _avatar(sender_id):
        gm = memberships_by_id.get(sender_id)
        return gm.session_avatar or '' if gm else ''

    return jsonify([{
        'id': m.id,
        'content': m.content,
        'is_me': m.sender_id == current_user.id,
        'sender_name': m.sender.proper_name,
        'sender_avatar': _avatar(m.sender_id),
        'timestamp': m.timestamp.strftime('%Y-%m-%d %H:%M'),
        'is_system_notification': m.is_system_notification,
    } for m in msgs])


@bp.route('/group/<int:group_id>/proposal', methods=['POST'])
@login_required
def group_submit_proposal(group_id):
    db = get_db()
    group = get_group_or_abort(group_id)
    if group is None or group.is_cancelled:
        flash('無法提出任務', 'danger')
        return redirect(url_for('dashboard_bp.dashboard'))

    restaurant = request.form.get('restaurant', '').strip()
    date_str = request.form.get('date_time', '').strip()
    if not restaurant or not date_str:
        flash('請填寫所有欄位', 'danger')
        return redirect(url_for('dashboard_bp.group_detail', group_id=group_id))

    from datetime import datetime
    proposal = GroupDateProposal(
        group_id=group_id,
        proposer_id=current_user.id,
        restaurant_name=restaurant,
        proposed_datetime=datetime.strptime(date_str, '%Y-%m-%dT%H:%M'),
    )
    db.add(proposal)
    db.commit()
    flash('任務提議已送出', 'success')
    return redirect(url_for('dashboard_bp.group_detail', group_id=group_id))


@bp.route('/group/<int:group_id>/proposal/<int:proposal_id>/delete', methods=['POST'])
@login_required
def group_delete_proposal(group_id, proposal_id):
    db = get_db()
    group = get_group_or_abort(group_id)
    proposal = db.get(GroupDateProposal, proposal_id)
    if group is None or proposal is None or proposal.group_id != group_id:
        flash('找不到該提議', 'danger')
        return redirect(url_for('dashboard_bp.group_detail', group_id=group_id))

    if proposal.proposer_id != current_user.id:
        flash('只有提議人可以刪除', 'danger')
        return redirect(url_for('dashboard_bp.group_detail', group_id=group_id))

    proposal.is_deleted = True
    db.commit()
    flash('提議已刪除', 'info')
    return redirect(url_for('dashboard_bp.group_detail', group_id=group_id))


@bp.route('/group/<int:group_id>/summary', methods=['POST'])
@login_required
def group_summary(group_id):
    db = get_db()
    group, _ = _get_group_and_membership(group_id)
    if group is None or not group.is_active:
        flash('無法提交總結', 'danger')
        return redirect(url_for('dashboard_bp.dashboard'))

    location = request.form.get('location', '').strip()
    meet_time_str = request.form.get('meet_time', '').strip()
    notes = request.form.get('notes', '').strip()

    if not location or not meet_time_str:
        flash('請填寫集合地點與時間', 'danger')
        return redirect(url_for('dashboard_bp.group_detail', group_id=group_id))

    from datetime import datetime as dt
    try:
        meet_time = dt.strptime(meet_time_str, '%Y-%m-%dT%H:%M')
    except ValueError:
        flash('時間格式錯誤', 'danger')
        return redirect(url_for('dashboard_bp.group_detail', group_id=group_id))

    group.meet_location = location
    group.meet_time = meet_time
    group.meet_notes = notes or None
    group.summary_submitted_by_id = current_user.id

    time_str = meet_time.strftime('%m/%d %H:%M')
    system_content = f"📌 {current_user.name} 幫大家做了個總結！\n📍 {location}　📅 {time_str}"
    if notes:
        system_content += f"\n💬 {notes}"
    sys_msg = GroupMessage(
        content=system_content,
        sender_id=current_user.id,
        group_id=group.id,
        is_system_notification=True,
    )
    db.add(sys_msg)
    db.flush()
    group.last_message_id = sys_msg.id
    db.commit()
    return redirect(url_for('dashboard_bp.group_detail', group_id=group_id))


@bp.route('/group/<int:group_id>/wish', methods=['POST'])
@login_required
def group_wish(group_id):
    db = get_db()
    group, my_membership = _get_group_and_membership(group_id)
    if group is None or group.is_cancelled or group.is_closed:
        return jsonify({'error': 'forbidden'}), 403

    if my_membership.clicked_wish_button:
        return jsonify({'already_clicked': True, 'score': current_user.companion_score}), 200

    my_membership.clicked_wish_button = True
    current_user.companion_score += 1

    from form_app.services.group_matching import compute_activity_label
    if current_user.activity_label != ActivityLabel.OBSERVER:
        current_user.activity_label = compute_activity_label(current_user.companion_score)

    db.commit()
    return jsonify({
        'success': True,
        'score': current_user.companion_score,
        'label': current_user.activity_label.value,
    })


@bp.route('/group/<int:group_id>/badge', methods=['POST'])
@login_required
def group_badge_submit(group_id):
    db = get_db()
    group, _ = _get_group_and_membership(group_id)
    if group is None or not group.is_feedback:
        flash('目前不在評分階段', 'danger')
        return redirect(url_for('dashboard_bp.dashboard'))

    valid_member_ids = {m.member_id for m in group.memberships}

    for key, value in request.form.items():
        if not key.startswith('badge_') or value != 'on':
            continue
        parts = key.split('_', 2)
        if len(parts) != 3:
            continue
        try:
            target_id = int(parts[1])
            badge_type = BadgeType[parts[2].upper()]
        except (ValueError, KeyError):
            continue
        if target_id == current_user.id or target_id not in valid_member_ids:
            continue
        db.add(GroupBadge(
            group_id=group_id,
            from_member_id=current_user.id,
            to_member_id=target_id,
            badge_type=badge_type,
        ))

    db.commit()
    flash('已送出你的祝福卡片！✨', 'success')
    return redirect(url_for('dashboard_bp.group_detail', group_id=group_id))


@bp.route('/reactivate', methods=['GET', 'POST'])
@login_required
def reactivate():
    """Observer self-reactivation — linked from the wake-up LINE message."""
    db = get_db()

    if current_user.activity_label != ActivityLabel.OBSERVER:
        flash('你目前已經是活躍狀態，無需重新啟動 🌱', 'info')
        return redirect(url_for('dashboard_bp.dashboard'))

    if request.method == 'POST':
        from form_app.services.group_matching import compute_activity_label
        current_user.activity_label = compute_activity_label(current_user.companion_score)
        current_user.observer_since = None
        current_user.observer_offense_count = 0
        db.commit()
        flash('歡迎回來！你已重新加入同行配對池 🌱', 'success')
        return redirect(url_for('dashboard_bp.dashboard'))

    return render_template('reactivate.html', current_user=current_user)


@bp.route('/profile')
@login_required
def profile():
    liff_url = None
    if settings.LIFF_ID:
        token = make_liff_token(current_user.phone_number)
        liff_url = f"https://liff.line.me/{settings.LIFF_ID}?token={token}"
    return render_template('profile.html', liff_url=liff_url)


@bp.route('/profile/change-password', methods=['POST'])
@login_required
def change_password():
    db = get_db()
    current_pw = request.form.get('current_password', '').strip()
    new_pw = request.form.get('new_password', '').strip()
    confirm_pw = request.form.get('confirm_password', '').strip()

    if not current_user.password_hash or not verify_password(current_user.password_hash, current_pw):
        flash('目前密碼不正確', 'danger')
        return redirect(url_for('dashboard_bp.profile'))

    if len(new_pw) < 6:
        flash('新密碼至少需要 6 個字元', 'danger')
        return redirect(url_for('dashboard_bp.profile'))

    if new_pw != confirm_pw:
        flash('兩次輸入的密碼不一致', 'danger')
        return redirect(url_for('dashboard_bp.profile'))

    user = db.get(Member, current_user.id)
    user.password_hash = hash_password(new_pw)
    db.commit()
    flash('密碼已成功更新', 'success')
    return redirect(url_for('dashboard_bp.profile'))


@bp.route('/profile/locks', methods=['POST'])
@login_required
def save_pref_locks():
    db = get_db()
    user = db.get(Member, current_user.id)
    user.pref_locks = {
        'height': request.form.get('lock_height') == '1',
        'region': request.form.get('lock_region') == '1',
    }
    db.commit()
    flash('偏好設定已更新', 'success')
    return redirect(url_for('dashboard_bp.profile'))
