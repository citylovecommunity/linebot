
from typing import Optional

from flask import (Blueprint, abort, flash, jsonify, redirect, render_template,
                   request, url_for)
from flask_login import current_user, login_required

from form_app.database import get_db
from form_app.models import (
    DateProposal, Matching, Member, Message,
    GroupMatching, GroupMessage, GroupDateProposal,
)
from form_app.services.security import verify_password, hash_password
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
        .filter(GroupMatching.members.any(Member.id == current_user.id))
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


def get_group_or_abort(group_id):
    db = get_db()
    group = db.get(GroupMatching, group_id)
    if not group:
        return None
    if not any(m.id == current_user.id for m in group.members):
        return None
    return group


@bp.route('/group/<int:group_id>', methods=['GET'])
@login_required
def group_detail(group_id):
    group = get_group_or_abort(group_id)
    if group is None:
        flash('群組不存在或您不是成員', 'danger')
        return redirect(url_for('dashboard_bp.dashboard'))

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    current_user.last_seen_at = now
    db = get_db()
    db.commit()

    return render_template('group_chat.html',
                           group=group,
                           messages=group.messages,
                           proposals=group.active_proposals,
                           current_user=current_user,
                           is_dev=settings.is_dev)


@bp.route('/group/<int:group_id>/send', methods=['POST'])
@login_required
def group_send_message(group_id):
    db = get_db()
    group = get_group_or_abort(group_id)
    if group is None:
        return jsonify({'error': 'forbidden'}), 403

    content = (request.json or {}).get('content', '') or request.form.get('message_content', '')
    if not content:
        return jsonify({'error': 'empty message'}), 400

    msg = GroupMessage(content=content, sender_id=current_user.id, group_id=group.id)
    db.add(msg)
    db.flush()
    group.last_message_id = msg.id
    db.commit()

    return jsonify({
        'id': msg.id,
        'content': msg.content,
        'is_me': True,
        'sender_name': current_user.proper_name,
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
    return jsonify([{
        'id': m.id,
        'content': m.content,
        'is_me': m.sender_id == current_user.id,
        'sender_name': m.sender.proper_name,
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


@bp.route('/profile')
@login_required
def profile():
    return render_template('profile.html')


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
