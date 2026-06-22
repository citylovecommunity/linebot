from datetime import datetime, timezone

from flask import Blueprint, render_template, request
from sqlalchemy.exc import IntegrityError

from form_app.config import settings
from form_app.database import get_db
from form_app.models import Invite, Member
from form_app.services.liff_token import make_liff_token
from form_app.services.security import hash_password

bp = Blueprint('profile_bp', __name__, url_prefix='/profile')


def _set_if_present(d: dict, key: str, value: str):
    if value:
        d[key] = value


def _populate_profile_info(user_info: dict, form):
    _set_if_present(user_info, '您目前的感情狀況', form.get('marital_status', '').strip())
    _set_if_present(user_info, '您有無小孩需要扶養', form.get('has_children', '').strip())
    _set_if_present(user_info, '會員之職業類別', form.get('job_category', '').strip())
    _set_if_present(user_info, '您的飲食習慣', form.get('diet', '').strip())
    _set_if_present(user_info, '宗教信仰', form.get('religion', '').strip())

    regions = form.getlist('date_regions')
    user_info['可約會地區 (可複選)'] = ','.join(regions) if regions else ''

    dealbreakers = form.getlist('dealbreakers')
    user_info['您完全無法接受的對象條件 (可複選)'] = ','.join(dealbreakers) if dealbreakers else '不設限'

    _set_if_present(user_info, '不能接受的飲食習慣', form.get('dealbreaker_diet', '').strip())
    _set_if_present(user_info, '無法接受之職業類別', form.get('dealbreaker_job', '').strip())
    _set_if_present(user_info, '無法接受的宗教信仰', form.get('dealbreaker_religion', '').strip())


@bp.route('/register/<token>', methods=['GET', 'POST'])
def register(token):
    session = get_db()
    invite = session.query(Invite).filter_by(token=token).first()

    if invite is None or not invite.is_valid:
        return render_template('profile_setup_invalid.html'), 410

    error = None

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone_number', '').strip()
        gender = request.form.get('gender', '').strip()
        birthday_str = request.form.get('birthday', '').strip()
        height_str = request.form.get('height', '').strip()

        birthday = None
        if birthday_str:
            try:
                birthday = datetime.strptime(birthday_str, '%Y-%m-%d').date()
            except ValueError:
                pass

        user_info = {}
        _populate_profile_info(user_info, request.form)
        if birthday:
            user_info.setdefault('您的出生年月日', birthday.strftime('%Y/%m/%d'))

        password_plain = request.form.get('password', '').strip()
        if not password_plain and birthday:
            password_plain = birthday.strftime('%Y%m%d')

        pref_fields = ['pref_min_height', 'pref_max_height', 'pref_oldest_birth_year', 'pref_youngest_birth_year']
        prefs = {}
        for f in pref_fields:
            val = request.form.get(f, '').strip()
            if val and val.lstrip('-').isdigit():
                prefs[f] = int(val)

        member = Member(
            name=name,
            phone_number=phone,
            gender=gender,
            birthday=birthday,
            height=int(height_str) if height_str and height_str.isdigit() else None,
            email=request.form.get('email', '').strip() or None,
            marital_status=request.form.get('marital_status') or None,
            fill_form_at=datetime.now(),
            user_info=user_info,
            password_hash=hash_password(password_plain) if password_plain else None,
            **prefs,
        )
        session.add(member)
        invite.used_at = datetime.now(timezone.utc)

        try:
            session.commit()
            liff_url = None
            if settings.LIFF_ID:
                token = make_liff_token(member.phone_number)
                liff_url = f"https://liff.line.me/{settings.LIFF_ID}?token={token}"
            return render_template('profile_setup_done.html', member=member, liff_url=liff_url)
        except IntegrityError:
            session.rollback()
            invite.used_at = None
            error = f'手機號碼 {phone} 已被使用，請確認後重試。'

    return render_template('profile_setup.html', invite=invite, error=error)
