import builtins
import smtplib
from datetime import UTC, datetime

import config as config_module
from flask import Flask

from models import time_utils
from routes import public as public_routes
from services import mail_service


def test_config_helpers_cover_env_and_secret_key_fallbacks(tmp_path, monkeypatch):
    monkeypatch.setenv('FLAG_ON', 'true')
    monkeypatch.setenv('INT_OK', '7')
    assert config_module._env_flag('FLAG_ON') is True
    assert config_module._env_flag('FLAG_MISSING', default=True) is True
    assert config_module._env_int('INT_OK', 1) == 7
    assert config_module._env_int('INT_BAD', 3) == 3

    secret_path = tmp_path / '.finora_secret_key'
    monkeypatch.setattr(config_module, 'LOCAL_SECRET_KEY_PATH', str(secret_path))
    secret_path.write_text('persisted-secret', encoding='utf-8')
    monkeypatch.delenv('SECRET_KEY', raising=False)
    assert config_module.get_or_create_local_secret_key() == 'persisted-secret'

    encrypted_payload = config_module._get_local_secret_cipher().encrypt(b'wrapped-secret').decode('utf-8')
    secret_path.write_text(
        f'{config_module.LOCAL_SECRET_KEY_PREFIX}{encrypted_payload}',
        encoding='utf-8',
    )
    assert config_module.get_or_create_local_secret_key() == 'wrapped-secret'

    monkeypatch.setenv('SECRET_KEY', 'env-secret')
    assert config_module.get_or_create_local_secret_key() == 'env-secret'


def test_config_secret_key_generation_handles_read_and_write_oserror(tmp_path, monkeypatch):
    monkeypatch.delenv('SECRET_KEY', raising=False)
    monkeypatch.setattr(config_module, 'LOCAL_SECRET_KEY_PATH', str(tmp_path / '.finora_secret_key'))

    real_open = builtins.open
    state = {'calls': 0}

    def flaky_open(*args, **kwargs):
        state['calls'] += 1
        if state['calls'] == 1:
            raise OSError('read failed')
        if state['calls'] == 2:
            raise OSError('write failed')
        return real_open(*args, **kwargs)

    monkeypatch.setattr(config_module.os.path, 'exists', lambda _path: True)
    monkeypatch.setattr(config_module, 'open', flaky_open, raising=False)
    generated = config_module.get_or_create_local_secret_key()
    assert isinstance(generated, str)
    assert len(generated) > 20


def test_config_generated_secret_is_derived_without_persisting(tmp_path, monkeypatch):
    monkeypatch.delenv('SECRET_KEY', raising=False)
    secret_path = tmp_path / '.finora_secret_key'
    monkeypatch.setattr(config_module, 'LOCAL_SECRET_KEY_PATH', str(secret_path))

    generated = config_module.get_or_create_local_secret_key()

    assert generated == config_module._derive_local_secret_key()
    assert secret_path.exists() is False


def test_time_utils_format_and_timezone_fallbacks(app):
    with app.app_context():
        app.config['APP_TIMEZONE'] = 'America/Sao_Paulo'
        naive_utc = datetime(2026, 3, 16, 15, 0, 0)
        localized = time_utils.to_app_datetime(naive_utc)
        assert localized is not None
        assert localized.tzinfo is not None
        assert time_utils.format_app_datetime(naive_utc)
        assert time_utils.format_app_date(naive_utc)
        assert time_utils.current_business_date()

    temp_app = Flask('tz-fallback')
    with temp_app.app_context():
        temp_app.config['APP_TIMEZONE'] = 'Invalid/Timezone'
        tz = time_utils.get_app_timezone()
        assert tz == UTC
        assert time_utils.format_app_datetime(None) == ''
        assert time_utils.format_app_date(None) == ''


def test_mail_service_covers_local_log_smtp_tls_ssl_and_failure(monkeypatch):
    app = Flask('mail-test')
    app.config.update(
        MAIL_SERVER='',
        MAIL_DEFAULT_SENDER='',
        MAIL_TIMEOUT_SECONDS=5,
    )

    logged = {}

    class Logger:
        def info(self, *args):
            logged['info'] = args

        def exception(self, *args):
            logged['exception'] = args

    app.logger = Logger()

    assert mail_service.send_email(app, '', 'Assunto', 'Corpo')['reason'] == 'missing_recipient'
    assert mail_service.send_email(app, 'dest@example.com', 'Assunto', 'Corpo')['delivery'] == 'log'
    assert 'info' in logged
    _message, *payload = logged['info']
    assert payload[-1] == len('Corpo')

    class FakeSMTP:
        def __init__(self, *_args, **_kwargs):
            self.started_tls = False
            self.logged_in = False
            self.sent = False

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def starttls(self):
            self.started_tls = True

        def login(self, *_args):
            self.logged_in = True

        def send_message(self, _message):
            self.sent = True

    smtp_instance = FakeSMTP()
    monkeypatch.setattr(mail_service.smtplib, 'SMTP', lambda *_args, **_kwargs: smtp_instance)
    app.config.update(
        MAIL_SERVER='smtp.example.com',
        MAIL_PORT=587,
        MAIL_USERNAME='user',
        MAIL_PASSWORD='pass',
        MAIL_USE_TLS=True,
        MAIL_USE_SSL=False,
        MAIL_DEFAULT_SENDER='noreply@example.com',
        MAIL_FROM_NAME='Finora',
    )
    result = mail_service.send_email(app, 'dest@example.com', 'Assunto', 'Corpo')
    assert result == {'ok': True, 'delivery': 'smtp'}
    assert smtp_instance.started_tls is True
    assert smtp_instance.logged_in is True
    assert smtp_instance.sent is True

    smtp_ssl_instance = FakeSMTP()
    monkeypatch.setattr(mail_service.smtplib, 'SMTP_SSL', lambda *_args, **_kwargs: smtp_ssl_instance)
    app.config['MAIL_USE_SSL'] = True
    app.config['MAIL_USE_TLS'] = False
    result = mail_service.send_email(app, 'dest@example.com', 'Assunto', 'Corpo')
    assert result == {'ok': True, 'delivery': 'smtp'}
    assert smtp_ssl_instance.sent is True

    class BrokenSMTP(FakeSMTP):
        def send_message(self, _message):
            raise smtplib.SMTPException('broken')

    monkeypatch.setattr(mail_service.smtplib, 'SMTP_SSL', lambda *_args, **_kwargs: BrokenSMTP())
    failure = mail_service.send_email(app, 'dest@example.com', 'Assunto', 'Corpo')
    assert failure['ok'] is False
    assert failure['reason'] == 'send_failed'
    assert 'exception' in logged


def test_public_routes_cover_redirect_and_update_branches(client, app, monkeypatch):
    with app.app_context():
        from database.db import db
        from models.user import User

        user = User(username='publicuser', email='publicuser@example.com', name='Public User')
        user.set_password('Password123')
        db.session.add(user)
        db.session.commit()

    client.post('/login', data={'identifier': 'publicuser', 'password': 'Password123'}, follow_redirects=True)
    response = client.get('/', follow_redirects=False)
    assert response.status_code == 302

    monkeypatch.setattr(public_routes, 'check_for_updates', lambda _app: {'error': 'boom'})
    response = client.post('/about/check-update', follow_redirects=True)
    assert response.status_code == 200
    assert b'boom' in response.data

    monkeypatch.setattr(
        public_routes,
        'check_for_updates',
        lambda _app: {'update_available': False, 'manifest': {'version': '1.3.0'}},
    )
    response = client.post('/about/check-update', follow_redirects=True)
    assert response.status_code == 200
    assert b'j\xc3\xa1 est\xc3\xa1 atualizada' in response.data

    monkeypatch.setattr(public_routes, 'apply_update', lambda *_args, **_kwargs: {'applied': False})
    response = client.post('/about/apply-update', follow_redirects=True)
    assert response.status_code == 200
    assert b'Nenhuma atualiza\xc3\xa7\xc3\xa3o aplic\xc3\xa1vel' in response.data

    monkeypatch.setattr(
        public_routes,
        'apply_update',
        lambda *_args, **_kwargs: {'applied': True, 'manifest': {'version': '1.3.1'}},
    )
    response = client.post('/about/apply-update', follow_redirects=True)
    assert response.status_code == 200
    assert b'1.3.1' in response.data

    legacy = client.get('/sobre', follow_redirects=False)
    assert legacy.status_code == 301
