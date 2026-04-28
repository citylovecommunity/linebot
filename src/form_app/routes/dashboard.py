
from typing import Optional

from flask import (Blueprint, abort, flash, jsonify, redirect, render_template,
                   request, url_for)
from flask_login import current_user, login_required

from form_app.database import get_db
from form_app.models import DateProposal, Matching, Member, Message
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

    return render_template('dashboard.html',
                           current_user=current_user,
                           missing_items=missing_items)


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
