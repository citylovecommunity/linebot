from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from shared.database.models import Member
# Import the decorator created in Step 3
from form_app.decorators import admin_required
from form_app.database import get_db


admin_bp = Blueprint('admin_bp', __name__, url_prefix='/admin')


@admin_bp.route('/dashboard')
@login_required
@admin_required  # This applies the protection
def admin_dashboard():
    # Fetch all users to display in a table
    all_users = Member.query.all()
    return render_template('admin_dashboard.html', users=all_users)


@admin_bp.route('/delete_user/<int:user_id>')
@login_required
@admin_required
def delete_user(user_id):
    db = get_db()
    user_to_delete = get_db(Member).query.get_or_404(user_id)

    # Prevent admin from deleting themselves
    if user_to_delete.id == current_user.id:
        flash("You cannot delete yourself!", "warning")
        return redirect(url_for('admin_bp.admin_dashboard'))

    db.session.delete(user_to_delete)
    db.session.commit()
    flash(f'User {user_to_delete.email} has been deleted.', 'success')
    return redirect(url_for('admin_bp.admin_dashboard'))
