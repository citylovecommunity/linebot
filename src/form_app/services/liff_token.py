from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from form_app.config import settings

_SALT = "liff-bind"
_MAX_AGE = 7 * 24 * 3600  # 7 days


def make_liff_token(phone_number: str) -> str:
    s = URLSafeTimedSerializer(settings.SECRET_KEY)
    return s.dumps(phone_number, salt=_SALT)


def load_liff_token(token: str) -> str | None:
    """Returns phone_number, or None if the token is invalid or expired."""
    s = URLSafeTimedSerializer(settings.SECRET_KEY)
    try:
        return s.loads(token, salt=_SALT, max_age=_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None
