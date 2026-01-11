from functools import wraps
from flask import request, redirect, url_for, jsonify
from database import get_db
from services.matching_services import get_matching_info_from_token


def match_transaction(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        token = kwargs.get('token')
        if 'token' in kwargs:
            del kwargs['token']

        db = get_db()
        match = get_matching_info_from_token(token)
        if not match:
            return jsonify({"error": "Not found"}), 404

        try:
            # Run the view function
            result = f(match, *args, **kwargs)

            # AUTOMATIC COMMIT
            db.commit()
            return result
        except Exception as e:
            db.rollback()
            raise e
    return wrapper
