from datetime import datetime

from flask import Blueprint, render_template, request
from sqlalchemy.exc import IntegrityError

from form_app.config import settings
from form_app.database import get_db
from form_app.models import Member
from form_app.services.liff_token import make_liff_token
from form_app.services.security import hash_password

bp = Blueprint('join_bp', __name__)


def _set_if_present(d: dict, key: str, value: str):
    if value:
        d[key] = value


@bp.route('/join', methods=['GET', 'POST'])
def join():
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
        _set_if_present(user_info, '您目前的感情狀況', request.form.get('marital_status', '').strip())
        _set_if_present(user_info, '您有無小孩需要扶養', request.form.get('has_children', '').strip())
        _set_if_present(user_info, '會員之職業類別', request.form.get('job_category', '').strip())
        _set_if_present(user_info, '您的飲食習慣', request.form.get('diet', '').strip())
        _set_if_present(user_info, '宗教信仰', request.form.get('religion', '').strip())

        regions = request.form.getlist('date_regions')
        user_info['可約會地區 (可複選)'] = ','.join(regions) if regions else ''

        dealbreakers = request.form.getlist('dealbreakers')
        user_info['您完全無法接受的對象條件 (可複選)'] = ','.join(dealbreakers) if dealbreakers else '不設限'
        _set_if_present(user_info, '不能接受的飲食習慣', request.form.get('dealbreaker_diet', '').strip())
        _set_if_present(user_info, '無法接受之職業類別', request.form.get('dealbreaker_job', '').strip())
        _set_if_present(user_info, '無法接受的宗教信仰', request.form.get('dealbreaker_religion', '').strip())

        if birthday:
            user_info.setdefault('您的出生年月日', birthday.strftime('%Y/%m/%d'))

        plan_months = request.form.get('plan_months', '').strip()
        if plan_months and plan_months.isdigit():
            user_info['購買的方案期數 /月（ 填寫純數字 ）'] = plan_months

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
        db = get_db()
        db.add(member)
        try:
            db.commit()
            liff_url = None
            if settings.LIFF_ID:
                token = make_liff_token(member.phone_number)
                liff_url = f"https://liff.line.me/{settings.LIFF_ID}?token={token}"
            return render_template('profile_setup_done.html', member=member, liff_url=liff_url)
        except IntegrityError:
            db.rollback()
            error = f'手機號碼 {phone} 已被使用，請確認後重試。'

    return render_template('join.html', error=error)
