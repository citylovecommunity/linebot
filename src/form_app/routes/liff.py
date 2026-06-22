from flask import Blueprint, jsonify, render_template, request
from sqlalchemy.exc import IntegrityError

from form_app.config import settings
from form_app.database import get_db
from form_app.models import Line_Info
from form_app.services.liff_token import load_liff_token

bp = Blueprint('liff_bp', __name__, url_prefix='/liff')


@bp.route('/bind')
def bind():
    return render_template('liff_bind.html', liff_id=settings.LIFF_ID)


@bp.route('/bind', methods=['POST'])
def bind_callback():
    data = request.get_json(silent=True) or {}
    token = data.get('token', '').strip()
    line_user_id = data.get('line_user_id', '').strip()

    if not token or not line_user_id:
        return jsonify(ok=False, error='missing_params'), 400

    phone_number = load_liff_token(token)
    if not phone_number:
        return jsonify(ok=False, error='invalid_or_expired_token'), 400

    db = get_db()
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
        # user_id unique constraint: this LINE account is already bound to another phone
        return jsonify(ok=False, error='line_account_already_used'), 409

    return jsonify(ok=True)
