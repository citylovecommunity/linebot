
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from form_app.database import get_db
from form_app.models import Member
from form_app.services.security import verify_password

bp = Blueprint('auth_bp', __name__)


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
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

        if user.is_admin:
            return redirect(url_for('admin_bp.admin_dashboard'))

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
