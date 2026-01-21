
from typing import Optional
from flask import (Blueprint, abort, flash, redirect, render_template, request,
                   url_for)
from flask_login import current_user, login_required

from form_app.database import get_db
from shared.database.models import DateProposal, Matching, Message

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
        abort(404)

    is_participant = (
        current_user.id == matching.subject_id or
        current_user.id == matching.object_id
    )

    if not is_participant:
        abort(403)

    return matching


@bp.route('/debug-user')
def debug_user():
    return {
        "is_authenticated": current_user.is_authenticated,
        "is_anonymous": current_user.is_anonymous,
        "is_active": current_user.is_active if hasattr(current_user, 'is_active') else "N/A",
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
