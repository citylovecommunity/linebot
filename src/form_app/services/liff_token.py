from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from form_app.config import settings


_LIFF_SALT = "liff-bind"
_LIFF_MAX_AGE = 7 * 24 * 3600  # 7 days

_PREF_SALT = "member-pref"
_PREF_MAX_AGE = 2 * 3600  # 2 hours


def make_liff_token(phone_number: str) -> str:
    s = URLSafeTimedSerializer(settings.SECRET_KEY)
    return s.dumps(phone_number, salt=_LIFF_SALT)


def load_liff_token(token: str) -> str | None:
    """Returns phone_number, or None if the token is invalid or expired."""
    s = URLSafeTimedSerializer(settings.SECRET_KEY)
    try:
        return s.loads(token, salt=_LIFF_SALT, max_age=_LIFF_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None


def make_member_token(member_id: int) -> str:
    s = URLSafeTimedSerializer(settings.SECRET_KEY)
    return s.dumps(member_id, salt=_PREF_SALT)


def load_member_token(token: str) -> int | None:
    """Returns member_id, or None if the token is invalid or expired."""
    s = URLSafeTimedSerializer(settings.SECRET_KEY)
    try:
        return s.loads(token, salt=_PREF_SALT, max_age=_PREF_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None
