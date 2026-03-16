import re
import uuid
from hashlib import sha256
import time

from flask import current_app, url_for
from flask_babel import gettext as _
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from database.db import db
from models.user import User
from services.db_resilience import run_idempotent_db_operation
from services.mail_service import send_email


MIN_PASSWORD_LENGTH = 8
RESET_PASSWORD_TOKEN_MAX_AGE_SECONDS = 3600
LOOKUP_RESPONSE_MIN_DURATION_SECONDS = 0.2


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
    payload = {
        'user_id': user.id,
        'email': user.email,
        'password_fingerprint': _build_password_fingerprint(user.password_hash),
        'password_reset_version': int(user.password_reset_version or 0),
    }
    return serializer.dumps(payload)


def generate_recovery_key():
    return str(uuid.uuid4()).replace('-', '').upper()[:16]


def build_recovery_key_email_body(user, recovery_key, reason):
    action_label = {
        'register': _('Sua conta foi criada com sucesso.'),
        'resend': _('Conforme solicitado, reenviamos sua chave de recuperação.'),
        'regenerate': _('Uma nova chave de recuperação foi gerada para sua conta.'),
    }.get(reason, _('Sua chave de recuperação está disponível abaixo.'))

    return (
        f"{_('Olá')}, {user.name or user.username}!\n\n"
        f'{action_label}\n\n'
        f"{_('Usuário')}: {user.username}\n"
        f"{_('Chave de recuperação')}: {recovery_key}\n"
        f"{_('Versão da chave')}: {int(user.recovery_key_version or 0)}\n\n"
        f"{_('Guarde esta chave em local seguro. Ela permite recuperar o acesso de forma offline.')}\n"
        f"{_('Se você acreditar que a chave foi comprometida, gere uma nova dentro do seu perfil.')}\n"
    )


def send_recovery_key_email(user, recovery_key, reason):
    subject = _('Finora - Sua chave de recuperação')
    body = build_recovery_key_email_body(user, recovery_key, reason)
    delivery = send_email(current_app, user.email, subject, body)
    if delivery.get('ok'):
        user.mark_recovery_key_sent()
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            current_app.logger.exception('Falha ao registrar envio da chave de recuperação.')
    return delivery


def send_reset_password_email(user):
    token = generate_reset_password_token(user)
    reset_url = build_reset_password_url(token)
    subject = _('Finora - Redefinição de senha')
    body = (
        f"{_('Olá')}, {user.name or user.username}!\n\n"
        f"{_('Recebemos uma solicitação para redefinir sua senha.')}\n"
        f"{_('Acesse o link abaixo para continuar:')}\n{reset_url}\n\n"
        f"{_('Este link expira em %(minutes)s minutos.', minutes=RESET_PASSWORD_TOKEN_MAX_AGE_SECONDS // 60)}\n"
    )
    return send_email(current_app, user.email, subject, body)


def build_reset_password_url(token):
    app_base_url = (current_app.config.get('APP_BASE_URL') or '').rstrip('/')
    if app_base_url:
        return f'{app_base_url}/reset_password/{token}'
    return url_for('auth.reset_password_token', token=token, _external=True)


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
    password_fingerprint = (data.get('password_fingerprint') or '').strip().lower()
    password_reset_version = data.get('password_reset_version')
    if not user_id or not email or not password_fingerprint or password_reset_version is None:
        return None, 'invalid'

    user = db.session.get(User, int(user_id))
    if not user or (user.email or '').strip().lower() != email:
        return None, 'invalid'
    if _build_password_fingerprint(user.password_hash) != password_fingerprint:
        return None, 'invalid'
    if int(user.password_reset_version or 0) != int(password_reset_version):
        return None, 'invalid'
    if (user.password_reset_token_hash or '').strip() == _hash_reset_token(token):
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


def _build_password_fingerprint(password_hash):
    if not password_hash:
        return ''
    return sha256(password_hash.encode('utf-8')).hexdigest()


def _hash_reset_token(token):
    return sha256((token or '').encode('utf-8')).hexdigest()


def consume_reset_password_token(user, token):
    user.mark_reset_token_consumed(_hash_reset_token(token))


def perform_signup_lookup_delay(start_time):
    elapsed = time.perf_counter() - start_time
    remaining = LOOKUP_RESPONSE_MIN_DURATION_SECONDS - elapsed
    if remaining > 0:
        time.sleep(remaining)
