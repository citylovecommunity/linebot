
from database import get_db
from flask import Blueprint, abort, redirect, render_template, request, url_for, flash
from sqlalchemy import or_, select

from shared.database.models import Matching, Member, Message, DateProposal

bp = Blueprint('dashboard_bp', __name__, url_prefix='/dashboard')


@bp.route('/<int:user_id>')
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


@bp.route('/<int:user_id>/<int:matching_id>', methods=['GET', 'POST'])
def matching_detail(user_id, matching_id):
    db = get_db()
    matching = db.query(Matching).where(Matching.id == matching_id).first()
    if not matching:
        abort(403)

    matching_users = [matching.subject_id, matching.object_id]
    if user_id not in matching_users:
        abort(403)

    current_user = matching.get_user(user_id)
    partner = matching.get_partner(user_id)

    # === HANDLING THE MESSAGE BOARD POST ===
    if request.method == 'POST' and 'message_content' in request.form:
        new_msg = Message(
            content=request.form['message_content'],
            user_id=user_id,
            matching=matching
        )
        db.add(new_msg)
        db.flush()

        matching.last_message_id = new_msg.id
        db.commit()
        return redirect(request.url)  # Reload to show new message

    proposal = db.query(DateProposal).filter_by(
        matching_id=matching.id).first()

    status_step = 1
    if matching.current_state == 'confirmed':
        status_step = 3
    elif proposal:
        status_step = 2

    is_proposal_pending = (proposal is not None)
    proposed_by_me = (proposal and proposal.proposer_id == current_user.id)

    return render_template('matching_dashboard.html',
                           matching=matching,
                           messages=matching.messages,
                           status_step=status_step,
                           proposal=proposal,
                           is_proposal_pending=is_proposal_pending,
                           proposed_by_me=proposed_by_me,
                           current_user=current_user,
                           partner=partner,
                           user_id=user_id)


@bp.route('/submit_proposal/<int:user_id>/<int:matching_id>', methods=['POST'])
def submit_proposal(user_id, matching_id):
    db = get_db()
    # 1. Validation logic
    restaurant = request.form.get('restaurant')
    date_str = request.form.get('date_time')

    if not restaurant or not date_str:
        flash("Please fill in all fields!", "danger")
        return redirect(url_for('.matching_detail', user_id=user_id, matching_id=matching_id))

    # 2. Save to DB (using the ORM strategy we discussed)
    from datetime import datetime
    new_proposal = DateProposal(
        matching_id=matching_id,
        proposer_id=user_id,
        restaurant_name=restaurant,
        proposed_datetime=datetime.strptime(
            date_str, '%Y-%m-%dT%H:%M'),  # adjust format
        booker_role=request.form.get('booker')
    )
    db.add(new_proposal)
    db.commit()

    # 3. Notify and Redirect
    flash("Proposal sent successfully!", "success")
    return redirect(url_for('.matching_detail', matching_id=matching_id, user_id=user_id))


@bp.route('/handle_proposal/<int:user_id>/<int:matching_id>', methods=['POST'])
def handle_proposal(matching_id, user_id):
    # 1. Fetch the Match and Proposal
    db = get_db()
    matching = db.query(Matching).where(Matching.id == matching_id).first()
    if not matching:
        abort(403)

    action = request.form.get('action')  # 'accept' or 'reject'

    # 3. Handle "ACCEPT"
    if action == 'accept':
        proposal = db.query(DateProposal).filter_by(
            matching_id=matching_id).first()
        # A. Transfer Data: Proposal -> Match
        matching.selected_date = proposal.proposed_datetime
        matching.selected_place = proposal.restaurant_name

        # B. Resolve "Who Books?" Logic
        # If proposer said "I will book" (me), then booker is proposer.
        # If proposer said "You book" (partner), then booker is current_user (the acceptor).
        if proposal.booker_role == 'me':
            matching.booker_id = proposal.proposer_id
        elif proposal.booker_role == 'partner':
            matching.booker_id = user_id
        else:
            matching.booker_id = None  # Walk-in / No booking

        # C. Update Status
        matching.current_state = 'confirmed'  # Or whatever enum you use

        # D. Create System Message (So it shows in chat)
        sys_msg = Message(
            matching=matching,
            user_id=user_id,  # Attributed to the acceptor
            content=f"✅ 接受在{proposal.restaurant_name}的約會提議!",
            is_system_notification=True
        )
        db.add(sys_msg)
        db.delete(proposal)

        flash("Date confirmed! See you there.", "success")

    # 4. Handle "REJECT"
    elif action == 'reject':
        # A. Create System Message
        sys_msg = Message(
            matching=matching,
            user_id=user_id,
            content="❌ 拒絕提議",
            is_system_notification=True
        )
        db.add(sys_msg)
        matching.selected_date = None
        matching.selected_place = None
        matching.current_state = 'date_pending'

        flash("Proposal declined.", "info")

    # 5. Cleanup (Crucial!)
    # Regardless of accept/reject, the 'pending proposal' is now gone.

    db.commit()

    return redirect(url_for('.matching_detail', matching_id=matching_id, user_id=user_id))
