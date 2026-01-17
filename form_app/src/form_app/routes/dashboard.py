
from flask import (Blueprint, abort, flash, redirect, render_template, request,
                   url_for)
from flask_login import current_user, login_required

from form_app.database import get_db
from shared.database.models import DateProposal, Matching, Member, Message

bp = Blueprint('dashboard_bp', __name__)


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
        abort(404)

    is_participant = (
        current_user.id == matching.subject_id or
        current_user.id == matching.object_id
    )

    if not is_participant:
        abort(403)

    return matching


@bp.route('/')
# @login_required
def dashboard():
    return render_template('dashboard.html',
                           current_user=current_user)


@bp.route('/debug-user')
def debug_user():
    return {
        "is_authenticated": current_user.is_authenticated,
        "is_anonymous": current_user.is_anonymous,
        "is_active": current_user.is_active if hasattr(current_user, 'is_active') else "N/A",
        "user_id": current_user.get_id() if hasattr(current_user, 'get_id') else "N/A"
    }


@bp.route('/<int:matching_id>', methods=['GET', 'POST'])
@login_required
def matching_detail(matching_id):
    matching = get_matching_or_abort(matching_id)
    partner = matching.get_partner(current_user.id)
    proposal = matching.ui_proposal
    messages = matching.messages
    if proposal is None:
        status_step = 1
    elif proposal.status == 'pending':
        status_step = 2
    elif proposal.status == 'confirmed':
        status_step = 3

    return render_template('matching_dashboard.html',
                           matching=matching,
                           status_step=status_step,
                           current_user=current_user,
                           partner=partner,
                           proposal=proposal,
                           messages=messages
                           )


@bp.route('/submit_message/<int:matching_id>', methods=['POST'])
@login_required
def submit_message(matching_id):
    db = get_db()
    matching = get_matching_or_abort(matching_id)
    new_msg = Message(
        content=request.form['message_content'],
        user_id=current_user.id,
        matching=matching
    )
    db.add(new_msg)
    db.flush()

    matching.last_message_id = new_msg.id
    db.commit()
    return redirect(request.referrer)


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


@bp.route('/handle_proposal/<int:matching_id>', methods=['POST'])
@login_required
def handle_proposal(matching_id):
    # 1. Fetch the Match and Proposal
    db = get_db()
    matching = get_matching_or_abort(matching_id)

    action = request.form.get('action')  # 'accept' or 'reject'
    proposal = matching.ui_proposal

    # 3. Handle "ACCEPT"
    if action == 'accept':

        # D. Create System Message (So it shows in chat)
        sys_msg = Message(
            matching=matching,
            user_id=current_user.id,  # Attributed to the acceptor
            content=f"✅ 接受在{proposal.restaurant_name}的約會提議!",
            is_system_notification=True
        )

        matching.ui_proposal.status = 'confirmed'
        db.add(sys_msg)

        flash("Date confirmed! See you there.", "success")

    # 4. Handle "REJECT"
    elif action == 'reject':
        # A. Create System Message
        sys_msg = Message(
            matching=matching,
            user_id=current_user.id,
            content=f"❌ {proposal.restaurant_name}提議已取消",
            is_system_notification=True
        )
        matching.ui_proposal.status = 'canceled'

        db.add(sys_msg)
        flash("Proposal declined.", "info")

    # 5. Cleanup (Crucial!)
    # Regardless of accept/reject, the 'pending proposal' is now gone.

    db.commit()

    return redirect(url_for('.matching_detail', matching_id=matching_id))
