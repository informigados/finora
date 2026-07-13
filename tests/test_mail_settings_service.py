import json

from flask import Flask

from services.mail_settings_service import (
    apply_desktop_mail_settings,
    get_mail_settings_summary,
    save_desktop_mail_settings,
)
from services import mail_settings_service


def _desktop_app(tmp_path):
    app = Flask('mail-settings-test')
    app.config.update(
        SECRET_KEY='test-secret',
        DESKTOP_MODE=True,
        MAIL_SETTINGS_PATH=str(tmp_path / 'settings' / 'mail.json'),
        MAIL_SERVER='',
        MAIL_PORT=587,
        MAIL_USERNAME='',
        MAIL_PASSWORD='',
        MAIL_USE_TLS=False,
        MAIL_USE_SSL=False,
        MAIL_DEFAULT_SENDER='',
        MAIL_FROM_NAME='Finora',
    )
    return app


def _valid_form(password='smtp-secret'):
    return {
        'mail_server': 'smtp.example.com',
        'mail_port': '465',
        'mail_username': 'sender@example.com',
        'mail_password': password,
        'mail_security': 'ssl',
        'mail_default_sender': 'sender@example.com',
        'mail_from_name': 'Finora',
    }


def test_desktop_mail_settings_are_encrypted_and_applied(tmp_path):
    app = _desktop_app(tmp_path)

    assert save_desktop_mail_settings(app, _valid_form()) is None

    raw_settings = (tmp_path / 'settings' / 'mail.json').read_text(encoding='utf-8')
    payload = json.loads(raw_settings)
    assert 'smtp-secret' not in raw_settings
    assert payload['password_encrypted']
    assert app.config['MAIL_PASSWORD'] == 'smtp-secret'
    assert app.config['MAIL_USE_SSL'] is True
    assert get_mail_settings_summary(app)['password_saved'] is True

    app.config.update(MAIL_SERVER='', MAIL_PASSWORD='', MAIL_DEFAULT_SENDER='')
    assert apply_desktop_mail_settings(app) is True
    assert app.config['MAIL_SERVER'] == 'smtp.example.com'
    assert app.config['MAIL_PASSWORD'] == 'smtp-secret'


def test_blank_password_preserves_existing_desktop_credential(tmp_path):
    app = _desktop_app(tmp_path)
    assert save_desktop_mail_settings(app, _valid_form()) is None
    original = json.loads(
        (tmp_path / 'settings' / 'mail.json').read_text(encoding='utf-8')
    )['password_encrypted']

    changed_form = _valid_form(password='')
    changed_form['mail_from_name'] = 'Finora Desktop'
    assert save_desktop_mail_settings(app, changed_form) is None

    payload = json.loads((tmp_path / 'settings' / 'mail.json').read_text(encoding='utf-8'))
    assert payload['password_encrypted'] == original
    assert payload['from_name'] == 'Finora Desktop'


def test_desktop_mail_settings_reject_invalid_values(tmp_path):
    app = _desktop_app(tmp_path)
    form = _valid_form()
    form['mail_port'] = '70000'
    assert save_desktop_mail_settings(app, form) == 'invalid_port'

    form = _valid_form()
    form['mail_server'] = 'bad host'
    assert save_desktop_mail_settings(app, form) == 'invalid_server'

    form = _valid_form()
    form['mail_default_sender'] = 'invalid'
    assert save_desktop_mail_settings(app, form) == 'invalid_sender'


def test_corrupt_desktop_mail_settings_do_not_break_startup(tmp_path):
    app = _desktop_app(tmp_path)
    settings_path = tmp_path / 'settings' / 'mail.json'
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text(
        json.dumps(
            {
                'server': 'smtp.example.com',
                'port': 'invalid',
                'default_sender': 'sender@example.com',
                'password_encrypted': 'invalid-token',
            }
        ),
        encoding='utf-8',
    )

    assert apply_desktop_mail_settings(app) is True
    assert app.config['MAIL_PORT'] == 587
    assert app.config['MAIL_PASSWORD'] == ''


def test_mail_settings_cover_safe_fallback_and_validation_edges(tmp_path, monkeypatch):
    app = _desktop_app(tmp_path)
    settings_path = tmp_path / 'settings' / 'mail.json'
    settings_path.parent.mkdir(parents=True)

    settings_path.write_text('{invalid', encoding='utf-8')
    assert apply_desktop_mail_settings(app) is False

    app.config['DESKTOP_MODE'] = False
    assert apply_desktop_mail_settings(app) is False
    assert get_mail_settings_summary(app) is None
    assert save_desktop_mail_settings(app, _valid_form()) == 'desktop_only'
    app.config['DESKTOP_MODE'] = True

    settings_path.write_text(
        json.dumps(
            {
                'server': 'smtp.example.com',
                'port': 70000,
                'security': 'invalid',
                'default_sender': 'sender@example.com',
            }
        ),
        encoding='utf-8',
    )
    assert apply_desktop_mail_settings(app) is True
    assert app.config['MAIL_PORT'] == 587
    assert app.config['MAIL_USE_TLS'] is True
    app.config.update(MAIL_USE_TLS=True, MAIL_USE_SSL=False)
    assert get_mail_settings_summary(app)['security'] == 'starttls'
    app.config.update(MAIL_USE_TLS=False, MAIL_USE_SSL=False)
    assert get_mail_settings_summary(app)['security'] == 'none'

    form = _valid_form()
    form['mail_port'] = 'invalid'
    assert save_desktop_mail_settings(app, form) == 'invalid_port'
    form = _valid_form()
    form['mail_security'] = 'invalid'
    assert save_desktop_mail_settings(app, form) == 'invalid_security'

    settings_path.unlink()
    form = _valid_form(password='')
    assert save_desktop_mail_settings(app, form) == 'missing_password'
    app.config['MAIL_SETTINGS_PATH'] = ''
    form = _valid_form()
    assert save_desktop_mail_settings(app, form) == 'storage_unavailable'

    app.config['MAIL_SETTINGS_PATH'] = str(settings_path)
    monkeypatch.setattr(
        mail_settings_service.os,
        'replace',
        lambda *_args: (_ for _ in ()).throw(OSError('blocked')),
    )
    assert save_desktop_mail_settings(app, _valid_form()) == 'persist_failed'
