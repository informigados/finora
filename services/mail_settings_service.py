import base64
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken


MAIL_SETTINGS_VERSION = 1
MAIL_SECURITY_OPTIONS = {'ssl', 'starttls', 'none'}
EMAIL_PATTERN = re.compile(r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')


def _settings_path(app):
    configured_path = (app.config.get('MAIL_SETTINGS_PATH') or '').strip()
    return Path(configured_path) if configured_path else None


def _cipher(app):
    secret = str(app.config.get('SECRET_KEY') or '')
    digest = hashlib.sha256(f'{secret}|finora-mail-settings-v1'.encode('utf-8')).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _read_payload(app):
    settings_path = _settings_path(app)
    if not settings_path or not settings_path.exists():
        return {}
    try:
        payload = json.loads(settings_path.read_text(encoding='utf-8'))
    except (OSError, ValueError, TypeError):
        app.logger.exception('Não foi possível ler as configurações locais de e-mail.')
        return {}
    return payload if isinstance(payload, dict) else {}


def _decrypt_password(app, payload):
    encrypted_password = (payload.get('password_encrypted') or '').strip()
    if not encrypted_password:
        return ''
    try:
        return _cipher(app).decrypt(encrypted_password.encode('utf-8')).decode('utf-8')
    except (InvalidToken, ValueError, TypeError):
        app.logger.error('A senha SMTP local não pôde ser descriptografada.')
        return ''


def _security_from_config(app):
    if app.config.get('MAIL_USE_SSL'):
        return 'ssl'
    if app.config.get('MAIL_USE_TLS'):
        return 'starttls'
    return 'none'


def _apply_payload(app, payload):
    security = (payload.get('security') or 'starttls').strip().lower()
    if security not in MAIL_SECURITY_OPTIONS:
        security = 'starttls'
    try:
        port = int(payload.get('port') or 587)
    except (TypeError, ValueError):
        port = 587
    if port < 1 or port > 65535:
        port = 587
    app.config.update(
        MAIL_SERVER=(payload.get('server') or '').strip(),
        MAIL_PORT=port,
        MAIL_USERNAME=(payload.get('username') or '').strip(),
        MAIL_PASSWORD=_decrypt_password(app, payload),
        MAIL_USE_TLS=security == 'starttls',
        MAIL_USE_SSL=security == 'ssl',
        MAIL_DEFAULT_SENDER=(payload.get('default_sender') or '').strip(),
        MAIL_FROM_NAME=(payload.get('from_name') or 'Finora').strip(),
        MAIL_SETTINGS_SOURCE='desktop',
    )


def apply_desktop_mail_settings(app):
    if not app.config.get('DESKTOP_MODE'):
        return False
    payload = _read_payload(app)
    if not payload:
        return False
    _apply_payload(app, payload)
    return True


def is_mail_delivery_configured(app):
    return bool(
        (app.config.get('MAIL_SERVER') or '').strip()
        and (app.config.get('MAIL_DEFAULT_SENDER') or '').strip()
    )


def get_mail_settings_summary(app):
    if not app.config.get('DESKTOP_MODE'):
        return None
    payload = _read_payload(app)
    return {
        'server': (app.config.get('MAIL_SERVER') or '').strip(),
        'port': int(app.config.get('MAIL_PORT') or 587),
        'username': (app.config.get('MAIL_USERNAME') or '').strip(),
        'default_sender': (app.config.get('MAIL_DEFAULT_SENDER') or '').strip(),
        'from_name': (app.config.get('MAIL_FROM_NAME') or 'Finora').strip(),
        'security': _security_from_config(app),
        'password_saved': bool(
            (payload.get('password_encrypted') or '').strip()
            or (app.config.get('MAIL_PASSWORD') or '')
        ),
        'configured': is_mail_delivery_configured(app),
    }


def save_desktop_mail_settings(app, form):
    if not app.config.get('DESKTOP_MODE'):
        return 'desktop_only'

    server = (form.get('mail_server') or '').strip()
    username = (form.get('mail_username') or '').strip()
    password = form.get('mail_password') or ''
    default_sender = (form.get('mail_default_sender') or '').strip().lower()
    from_name = (form.get('mail_from_name') or 'Finora').strip()
    security = (form.get('mail_security') or 'starttls').strip().lower()

    try:
        port = int(form.get('mail_port') or 0)
    except (TypeError, ValueError):
        return 'invalid_port'

    if not server or any(character.isspace() for character in server):
        return 'invalid_server'
    if port < 1 or port > 65535:
        return 'invalid_port'
    if security not in MAIL_SECURITY_OPTIONS:
        return 'invalid_security'
    if not default_sender or not EMAIL_PATTERN.match(default_sender):
        return 'invalid_sender'

    existing_payload = _read_payload(app)
    encrypted_password = (existing_payload.get('password_encrypted') or '').strip()
    if password:
        encrypted_password = _cipher(app).encrypt(password.encode('utf-8')).decode('utf-8')
    if username and not encrypted_password:
        return 'missing_password'

    payload = {
        'version': MAIL_SETTINGS_VERSION,
        'server': server,
        'port': port,
        'username': username,
        'password_encrypted': encrypted_password,
        'security': security,
        'default_sender': default_sender,
        'from_name': from_name or 'Finora',
    }

    settings_path = _settings_path(app)
    if not settings_path:
        return 'storage_unavailable'
    temporary_path = None
    try:
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode='w',
            encoding='utf-8',
            dir=settings_path.parent,
            prefix='.mail-settings-',
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            json.dump(payload, temporary_file, ensure_ascii=False, indent=2)
            temporary_file.write('\n')
        os.chmod(temporary_path, 0o600)
        os.replace(temporary_path, settings_path)
    except OSError:
        app.logger.exception('Não foi possível salvar as configurações locais de e-mail.')
        if temporary_path and temporary_path.exists():
            temporary_path.unlink(missing_ok=True)
        return 'persist_failed'

    _apply_payload(app, payload)
    return None
