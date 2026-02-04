
from flask import Blueprint, flash, redirect, render_template, request, url_for, current_app, abort
from flask_login import (current_user, login_required,
                         login_user, logout_user)

from form_app.database import get_db
from shared.database.models import Member
from shared.security import verify_password

bp = Blueprint('auth_bp', __name__)


@bp.route('/auto-login/<int:user_id>')
def auto_login(user_id):
    # SAFETY NET: Strictly forbid this in production
    if not current_app.debug:
        abort(404)

    # 1. Grab a hardcoded "dev" user or the first user in the DB
    db = get_db()
    dev_user = db.query(Member).get(user_id)

    # 2. Log them in programmatically
    if dev_user:
        login_user(dev_user)
        # Redirect to where you want to work
        return redirect(url_for('dashboard_bp.dashboard'))

    return "Dev user not found", 404


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        # Check logic here too in case they are already logged in
        if current_user.is_admin:
            return redirect(url_for('admin_bp.admin_dashboard'))
        return redirect(url_for('dashboard_bp.dashboard'))

    if request.method == 'POST':
        phone = request.form.get('phone')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False

        db = get_db()
        user = db.query(Member).where(Member.phone_number == phone).first()

        if not user or not verify_password(user.password_hash, password):
            flash('Please check your login details and try again.', 'danger')
            return redirect(url_for('auth_bp.login'))

        login_user(user, remember=remember)

        # --- NEW ADMIN LOGIC HERE ---
        if user.is_admin:
            return redirect(url_for('admin_bp.admin_dashboard'))
        # ----------------------------

        next_page = request.args.get('next')
        if not next_page or not next_page.startswith('/'):
            next_page = url_for('index')

        return redirect(next_page)

    return render_template('login.html')


@bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth_bp.login'))
