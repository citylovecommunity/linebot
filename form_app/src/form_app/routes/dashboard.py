
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
    return render_template('dashboard.html',
                           current_user=current_user)


@bp.route('/<int:matching_id>', methods=['GET', 'POST'])
@login_required
def matching_detail(matching_id):
    matching = get_matching_or_abort(matching_id)

    # --- PART 1: Handle Pending Logic (Double Opt-In) ---
    if matching.is_pending:

        # 1. Handle Button Clicks (POST)
        if request.method == 'POST':
            action = request.form.get('action')

            if action == 'reject':
                # Single veto rule: One rejection cancels the whole match
                matching.status = 'cancelled'
                # db.session.commit()
                flash('Matching rejected.', 'info')
                return redirect(url_for('bp.index'))

            elif action == 'agree':
                # Double opt-in logic
                # activate_by should record this user's 'yes'
                # AND update matching.status to 'active' ONLY if both have said yes.
                matching.activate_by(current_user.id)
                # db.session.commit()

                # Check status immediately after the update
                if matching.is_active:
                    flash('It\'s a match! Dashboard is now active.', 'success')
                    # Redirect to self -> falls through to Part 2 below
                    return redirect(url_for('bp.matching_detail', matching_id=matching.id))
                else:
                    flash('Accepted! Waiting for partner to confirm.', 'success')
                    # Redirect to self -> caught by Part 1 "Waiting" view below
                    return redirect(url_for('bp.matching_detail', matching_id=matching.id))

        # 2. Handle View (GET)
        # We need to know if THIS user has already agreed
        # Assuming you have a method/property checking the association table or column
        if matching.has_accepted(current_user.id):
            # User already clicked agree, but match is still pending (partner hasn't clicked)
            return render_template('matching_pending_waiting.html', matching=matching)
        else:
            # User has not voted yet
            return render_template('matching_pending_decision.html', matching=matching)

    # --- PART 2: Handle Active State (Existing Logic) ---
    # If we are here, the matching is NOT pending. It acts as the "Active" dashboard.

    partner = matching.get_partner(current_user.id)
    proposal = matching.ui_proposal
    messages = matching.messages

    status_step = 1
    if proposal:
        if proposal.is_pending:
            status_step = 2
        elif proposal.is_confirmed:
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
            user_id=current_user,  # Attributed to the acceptor
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
            user=current_user,
            content=f"❌ {proposal.restaurant_name}提議已取消",
            is_system_notification=True
        )
        proposal.delete()

        db.add(sys_msg)
        flash("Proposal declined.", "info")

    db.commit()

    return redirect(url_for('.matching_detail', matching_id=matching_id))
