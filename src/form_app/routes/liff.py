from flask import Blueprint, jsonify, render_template, request
from sqlalchemy.exc import IntegrityError

from form_app.config import settings
from form_app.database import get_db
from form_app.models import Line_Info, Member
from form_app.services.liff_token import load_liff_token, make_member_token

bp = Blueprint('liff_bp', __name__, url_prefix='/liff')


@bp.route('/bind')
def bind():
    return render_template('liff_bind.html', liff_id=settings.LIFF_ID)


@bp.route('/bind', methods=['POST'])
def bind_callback():
    data = request.get_json(silent=True) or {}
    line_user_id = data.get('line_user_id', '').strip()
    token = data.get('token', '').strip()
    phone_number = data.get('phone_number', '').strip()

    if not line_user_id:
        return jsonify(ok=False, error='missing_params'), 400

    db = get_db()

    if token:
        phone_number = load_liff_token(token)
        if not phone_number:
            return jsonify(ok=False, error='invalid_or_expired_token'), 400
    elif phone_number:
        member = db.query(Member).filter_by(phone_number=phone_number).first()
        if not member:
            return jsonify(ok=False, error='member_not_found'), 404
    else:
        return jsonify(ok=False, error='missing_params'), 400

    existing = db.query(Line_Info).filter_by(phone_number=phone_number).first()
    if existing:
        if existing.user_id == line_user_id:
            return jsonify(ok=True, already_bound=True)
        existing.user_id = line_user_id
    else:
        db.add(Line_Info(phone_number=phone_number, user_id=line_user_id))

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return jsonify(ok=False, error='line_account_already_used'), 409

    return jsonify(ok=True)


@bp.route('/preferences-link', methods=['POST'])
def preferences_link():
    """Called by the LIFF page to exchange a LINE userId for a preferences URL."""
    data = request.get_json(silent=True) or {}
    line_user_id = data.get('line_user_id', '').strip()
    if not line_user_id:
        return jsonify(ok=False, error='missing_params'), 400

    db = get_db()
    line_info = db.query(Line_Info).filter_by(user_id=line_user_id).first()
    if not line_info:
        return jsonify(ok=False, error='not_bound'), 404

    member = db.query(Member).filter_by(phone_number=line_info.phone_number).first()
    if not member:
        return jsonify(ok=False, error='member_not_found'), 404

    token = make_member_token(member.id)
    return jsonify(ok=True, url=f'{settings.APP_URL}/dashboard/preferences/{token}')
