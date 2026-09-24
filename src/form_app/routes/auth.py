
from linebot import LineBotApi
from linebot.models import TextSendMessage

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from form_app.config import settings
from form_app.database import get_db
from form_app.extensions import line_bot_helper
from form_app.models import Member
from form_app.services.liff_token import make_reset_token, load_reset_token
from form_app.services.security import hash_password, verify_password

bp = Blueprint('auth_bp', __name__)


def _send_reset_link(user: Member) -> None:
    """Push a password-reset link to the member via LINE. No-ops if not bound to LINE."""
    if settings.is_dev:
        target = settings.LINE_TEST_USER_ID
    else:
        target = user.line_info.user_id if user.line_info else None
    if not target:
        return

    token = make_reset_token(user.id)
    reset_url = f"{settings.APP_URL}/reset-password/{token}"
    text = f"您好，這是您的密碼重設連結（30 分鐘內有效）：\n{reset_url}"

    line_bot_api = LineBotApi(line_bot_helper.configuration.access_token)
    try:
        line_bot_api.push_message(target, TextSendMessage(text=text))
    except Exception as e:
        print(f"[auth] password reset LINE push failed for member {user.id}: {e}")


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for('admin_bp.admin_dashboard'))
        return redirect(url_for('dashboard_bp.dashboard'))

    if request.method == 'POST':
        phone = request.form.get('phone')
        password = request.form.get('password')

        db = get_db()
        user = db.query(Member).where(Member.phone_number == phone).first()

        if not user or not verify_password(user.password_hash, password):
            flash('Please check your login details and try again.', 'danger')
            return redirect(url_for('auth_bp.login'))

        # Always issue the long-lived remember-me cookie: users open partner
        # profile links (target="_blank") inside LINE's in-app browser, which
        # frequently drops the plain session cookie on tab switches. Relying
        # on an opt-in checkbox caused unexpected logouts for anyone who
        # didn't check it.
        login_user(user, remember=True)

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


@bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        phone = request.form.get('phone', '').strip()
        db = get_db()
        user = db.query(Member).filter(Member.phone_number == phone).first()
        if user:
            _send_reset_link(user)

        # Always show the same message, whether or not the phone number is
        # registered or bound to LINE, so this can't be used to probe accounts.
        flash('若該手機號碼已註冊並綁定 LINE，將會收到密碼重設連結，請至 LINE 官方帳號查看訊息。', 'info')
        return redirect(url_for('auth_bp.login'))

    return render_template('forgot_password.html')


@bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    member_id = load_reset_token(token)
    if member_id is None:
        return render_template('reset_link_expired.html'), 410

    db = get_db()
    user = db.get(Member, member_id)
    if not user:
        return render_template('reset_link_expired.html'), 410

    error = None
    if request.method == 'POST':
        new_password = request.form.get('new_password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()

        if len(new_password) < 6:
            error = '新密碼至少需要 6 個字元'
        elif new_password != confirm_password:
            error = '兩次輸入的密碼不一致'
        else:
            user.password_hash = hash_password(new_password)
            db.commit()
            login_user(user, remember=True)
            flash('密碼已重設，歡迎回來！', 'success')
            if user.is_admin:
                return redirect(url_for('admin_bp.admin_dashboard'))
            return redirect(url_for('dashboard_bp.dashboard'))

    return render_template('reset_password.html', token=token, error=error)
