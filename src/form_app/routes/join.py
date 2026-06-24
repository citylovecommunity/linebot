from datetime import datetime

import cloudinary
import cloudinary.uploader
from flask import Blueprint, redirect, render_template, request, url_for
from sqlalchemy.exc import IntegrityError

from form_app.campaigns import get_campaign
from form_app.config import settings
from form_app.database import get_db
from form_app.models import Member
from form_app.services.liff_token import make_liff_token
from form_app.services.security import hash_password

cloudinary.config(cloud_name=settings.CLOUDINARY_CLOUD_NAME)

bp = Blueprint('join_bp', __name__)


def _set_if_present(d: dict, key: str, value: str):
    if value:
        d[key] = value


@bp.route('/join')
def join_default():
    return redirect(url_for('join_bp.join', slug='default'))


@bp.route('/join/<slug>', methods=['GET', 'POST'])
def join(slug: str):
    campaign = get_campaign(slug)
    error = None

    if request.method == 'POST':
        name         = request.form.get('name', '').strip()
        phone        = request.form.get('phone_number', '').strip()
        gender       = request.form.get('gender', '').strip()
        birthday_str = request.form.get('birthday', '').strip()
        height_str   = request.form.get('height', '').strip()
        campaign_slug = request.form.get('campaign', slug)

        birthday = None
        if birthday_str:
            try:
                birthday = datetime.strptime(birthday_str, '%Y-%m-%d').date()
            except ValueError:
                pass

        user_info = {}

        # Step 2 fields
        _set_if_present(user_info, '您目前的感情狀況',   request.form.get('marital_status', '').strip())
        _set_if_present(user_info, '您有無小孩需要扶養', request.form.get('has_children', '').strip())
        _set_if_present(user_info, '會員之職業類別',     request.form.get('job_category', '').strip())
        _set_if_present(user_info, '宗教信仰',           request.form.get('religion', '').strip())
        _set_if_present(user_info, '簡單介紹自己',       request.form.get('self_intro', '').strip())

        interests = request.form.getlist('interests')
        if interests:
            user_info['興趣'] = ','.join(interests)

        # Step 3 fields
        regions = request.form.getlist('date_regions')
        user_info['可約會地區 (可複選)'] = ','.join(regions) if regions else ''

        if birthday:
            user_info.setdefault('您的出生年月日', birthday.strftime('%Y/%m/%d'))

        photo = request.files.get('profile_photo')
        if photo and photo.filename:
            result = cloudinary.uploader.unsigned_upload(
                photo,
                settings.CLOUDINARY_UPLOAD_PRESET,
                folder="citylove/members",
            )
            user_info['相片網址'] = result['secure_url']

        password_plain = birthday.strftime('%Y%m%d') if birthday else None

        member = Member(
            name=name,
            phone_number=phone,
            gender=gender,
            birthday=birthday,
            height=int(height_str) if height_str and height_str.isdigit() else None,
            email=request.form.get('email', '').strip() or None,
            marital_status=request.form.get('marital_status') or None,
            fill_form_at=datetime.now(),
            join_campaign=campaign_slug,
            user_info=user_info,
            password_hash=hash_password(password_plain) if password_plain else None,
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

    return render_template('join.html', campaign=campaign, error=error)
