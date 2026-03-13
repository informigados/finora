import re
from datetime import UTC, datetime

from flask import current_app
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from database.db import db
from models.user import User
from services.db_resilience import run_idempotent_db_operation


MIN_PASSWORD_LENGTH = 8
RESET_PASSWORD_TOKEN_MAX_AGE_SECONDS = 3600


def utcnow_naive():
    return datetime.now(UTC).replace(tzinfo=None)


def is_valid_email(email):
    pattern = r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'
    return re.match(pattern, email) is not None


def is_strong_password(password):
    if len(password or '') < MIN_PASSWORD_LENGTH:
        return False
    has_upper = any(char.isupper() for char in password)
    has_lower = any(char.islower() for char in password)
    has_digit = any(char.isdigit() for char in password)
    return has_upper and has_lower and has_digit


def build_reset_password_serializer():
    return URLSafeTimedSerializer(
        current_app.config['SECRET_KEY'],
        salt='finora-reset-password',
    )


def generate_reset_password_token(user):
    serializer = build_reset_password_serializer()
    payload = {'user_id': user.id, 'email': user.email}
    return serializer.dumps(payload)


def resolve_user_from_reset_token(token):
    serializer = build_reset_password_serializer()
    try:
        data = serializer.loads(token, max_age=RESET_PASSWORD_TOKEN_MAX_AGE_SECONDS)
    except SignatureExpired:
        return None, 'expired'
    except BadSignature:
        return None, 'invalid'

    user_id = data.get('user_id')
    email = (data.get('email') or '').strip().lower()
    if not user_id or not email:
        return None, 'invalid'

    user = db.session.get(User, int(user_id))
    if not user or (user.email or '').strip().lower() != email:
        return None, 'invalid'

    return user, None


def find_user_by_identifier(identifier):
    normalized = (identifier or '').strip()
    if not normalized:
        return None

    def _query_user():
        return User.query.filter(
            (User.email == normalized.lower()) | (User.username == normalized)
        ).first()

    return run_idempotent_db_operation(_query_user)


def commit_auth_security_state():
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception('Falha ao persistir estado de segurança de autenticação.')
