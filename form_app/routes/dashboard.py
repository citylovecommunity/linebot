
from database import get_db
from flask import Blueprint, abort, redirect, render_template, request
from sqlalchemy import or_, select

from shared.database.models import Matching, Member, Message

bp = Blueprint('dashboard_bp', __name__)


@bp.route('/match/<int:user_id>')
def dashboard(user_id):
    db = get_db()
    current_user = db.query(Member).where(Member.id == user_id).first()
    if not current_user:
        abort(403)

    stmt = select(Matching).where(
        or_(
            Matching.subject_id == user_id,
            Matching.object_id == user_id
        )
    )
    matches = db.execute(stmt).scalars().all()

    return render_template('dashboard.html',
                           user_id=user_id,
                           matches=matches)


@bp.route('/match/<int:user_id>/<int:match_id>', methods=['GET', 'POST'])
def match_detail(user_id, match_id):
    db = get_db()
    match = db.query(Matching).where(Matching.id == match_id).first()
    if not match:
        abort(403)

    matching_users = [match.subject_id, match.object_id]
    if user_id not in matching_users:
        abort(403)

    matching_users.remove(user_id)
    current_user = db.query(Member).where(Member.id == user_id).first()
    partner = db.query(Member).where(Member.id == matching_users[0]).first()

    # === HANDLING THE MESSAGE BOARD POST ===
    if request.method == 'POST' and 'message_content' in request.form:
        new_msg = Message(
            content=request.form['message_content'],
            user_id=user_id,
            match=match
        )
        db.add(new_msg)
        db.commit()
        return redirect(request.url)  # Reload to show new message

    # === DETERMINE "NEXT ACTION" PROMPT ===
    action_required = False
    action_type = None  # 'accept', 'book', 'pay'

    # Logic: Who needs to act right now?
    if match.current_state == 'invitation_waiting' and user_id == match.invited_id:
        action_required = True
        action_type = 'accept_reject'

    elif match.current_state == 'booking_phase' and user_id == match.inviter_id:
        action_required = True
        action_type = 'book_restaurant'

    return render_template('matching_dashboard.html',
                           match=match,
                           messages=match.messages,
                           action_required=action_required,
                           action_type=action_type,
                           current_user=current_user,
                           partner=partner)
