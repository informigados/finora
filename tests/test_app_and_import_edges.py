import io
import logging
import socket
from pathlib import Path

import openpyxl
import pytest
from flask import Flask
from werkzeug.datastructures import FileStorage

import app as app_module
from app import (
    create_app,
    ensure_runtime_schema_compatibility,
    find_free_port,
    open_browser,
    schedule_browser_open,
    seed_default_user,
)
from config import config
from database.db import db
from models.user import User
from services.import_service import ImportValidationError, import_finances_from_file
from services.logging_utils import configure_application_logging, request_id_context

GENERIC_RESPONSE_WARNING_MARKER = b'resposta generica'


def test_set_language_redirects_to_last_safe_page(client):
    with client.session_transaction() as session:
        session['language_redirect_target'] = '/about'

    response = client.get('/set_language/en', follow_redirects=False)

    assert response.status_code == 302
    assert response.headers['Location'].endswith('/about')


def test_set_language_preserves_last_safe_query_string(client):
    with client.session_transaction() as session:
        session['language_redirect_target'] = '/dashboard/2026/3?page=2'

    response = client.get('/set_language/en', follow_redirects=False)

    assert response.status_code == 302
    assert response.headers['Location'].endswith('/dashboard/2026/3?page=2')


def test_set_language_rejects_unsafe_session_redirect_target(client):
    with client.session_transaction() as session:
        session['language_redirect_target'] = 'http://evil.example/phish'

    response = client.get('/set_language/en', follow_redirects=False)

    assert response.status_code == 302
    assert response.headers['Location'].endswith('/')


def test_request_id_header_is_generated_when_missing(client):
    response = client.get('/health')

    assert response.status_code == 200
    assert response.headers['X-Request-ID']


def test_request_id_header_reuses_incoming_value(client):
    response = client.get('/health', headers={'X-Request-ID': 'request-123'})

    assert response.status_code == 200
    assert response.headers['X-Request-ID'] == 'request-123'


def test_configure_application_logging_writes_rotating_file(tmp_path):
    app = Flask('logging-test')
    app.config.update(
        LOG_LEVEL='INFO',
        SQLALCHEMY_LOG_LEVEL='WARNING',
        WERKZEUG_LOG_LEVEL='INFO',
        WAITRESS_LOG_LEVEL='INFO',
        LOG_FORMAT='%(levelname)s request_id=%(request_id)s %(message)s',
        LOG_TO_FILE=True,
        LOG_DIRECTORY=str(tmp_path),
        LOG_FILE_NAME='finora.log',
        LOG_MAX_BYTES=4096,
        LOG_BACKUP_COUNT=2,
    )
    app.logger.handlers.clear()

    configure_application_logging(app)
    token = request_id_context.set('req-file-123')
    try:
        app.logger.info('arquivo de log ativo')
    finally:
        request_id_context.reset(token)

    for handler in app.logger.handlers:
        handler.flush()
        handler.close()

    content = (Path(tmp_path) / 'finora.log').read_text(encoding='utf-8')
    assert 'arquivo de log ativo' in content
    assert 'request_id=req-file-123' in content


def test_configure_application_logging_keeps_sqlalchemy_quiet_by_default():
    app = Flask('logging-level-test')
    app.config.update(
        LOG_LEVEL='INFO',
        SQLALCHEMY_LOG_LEVEL='WARNING',
        WERKZEUG_LOG_LEVEL='INFO',
        WAITRESS_LOG_LEVEL='INFO',
    )

    configure_application_logging(app)

    assert logging.getLogger('sqlalchemy.engine').level == logging.WARNING


def test_health_endpoint_reports_degraded_when_db_fails(client, monkeypatch):
    def raise_db_down(*_args, **_kwargs):
        raise RuntimeError('db down')

    monkeypatch.setattr(app_module.db.session, 'execute', raise_db_down)
    response = client.get('/health')

    assert response.status_code == 503
    assert response.get_json() == {'status': 'degraded', 'database': 'error'}


def test_create_app_requires_secret_key_in_production(monkeypatch):
    original_secret = config['production'].SECRET_KEY
    config['production'].SECRET_KEY = None
    try:
        with pytest.raises(RuntimeError):
            create_app('production')
    finally:
        config['production'].SECRET_KEY = original_secret


def test_seed_default_user_creates_user_when_enabled(app, monkeypatch):
    with app.app_context():
        db.create_all()
        app.config['TESTING'] = False
        app.config['ENABLE_DEFAULT_USER_SEED'] = True
        monkeypatch.setenv('DEFAULT_USER_NAME', 'Seed User')
        monkeypatch.setenv('DEFAULT_USER_USERNAME', 'seeduser')
        monkeypatch.setenv('DEFAULT_USER_EMAIL', 'seed@example.com')
        monkeypatch.setenv('DEFAULT_USER_PASSWORD', 'SeedPassword123')

        seed_default_user(app)

        seeded_user = User.query.filter_by(username='seeduser').first()
        assert seeded_user is not None
        assert seeded_user.email == 'seed@example.com'
        assert seeded_user.name == 'Seed User'


def test_forgot_password_page_does_not_render_privacy_warning(client):
    response = client.get('/forgot_password')

    assert response.status_code == 200
    assert GENERIC_RESPONSE_WARNING_MARKER not in response.data


def test_ensure_runtime_schema_compatibility_is_noop_under_testing(app):
    with app.app_context():
        ensure_runtime_schema_compatibility(app)


def test_find_free_port_returns_available_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as temp_socket:
        temp_socket.bind(('127.0.0.1', 0))
        occupied_port = temp_socket.getsockname()[1]
        free_port = find_free_port(occupied_port)

    assert isinstance(free_port, int)
    assert free_port >= occupied_port

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as test_socket:
        test_socket.bind(('127.0.0.1', free_port))


def test_open_browser_delegates_to_webbrowser(monkeypatch):
    opened = {}
    monkeypatch.setattr(
        'webbrowser.open',
        lambda url, new=0, autoraise=True: opened.__setitem__(
            'call',
            (url, new, autoraise),
        ),
    )

    open_browser(5050)

    assert opened['call'] == ('http://127.0.0.1:5050/', 0, True)


def test_schedule_browser_open_starts_timer_once(monkeypatch):
    calls = {}

    class FakeTimer:
        def __init__(self, delay, callback):
            calls['delay'] = delay
            calls['callback'] = callback

        def start(self):
            calls['started'] = True

    monkeypatch.setattr(app_module, 'Timer', FakeTimer)
    monkeypatch.setattr(app_module, '_acquire_browser_launch_guard', lambda _port: True)
    monkeypatch.setenv('FINORA_AUTO_OPEN_BROWSER', '1')

    assert schedule_browser_open(5050) is True
    assert calls == {
        'delay': 1.5,
        'callback': calls['callback'],
        'started': True,
    }


def test_schedule_browser_open_skips_when_guard_is_active(monkeypatch):
    monkeypatch.setattr(app_module, '_acquire_browser_launch_guard', lambda _port: False)
    monkeypatch.setenv('FINORA_AUTO_OPEN_BROWSER', '1')

    assert schedule_browser_open(5050) is False


def test_schedule_browser_open_can_be_disabled(monkeypatch):
    monkeypatch.setenv('FINORA_AUTO_OPEN_BROWSER', '0')
    monkeypatch.setattr(
        app_module,
        'Timer',
        lambda *_args, **_kwargs: pytest.fail('Timer should not be created'),
    )

    assert schedule_browser_open(5050) is False


def test_import_finances_from_xlsx_supports_aliases():
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(['Descrição', 'Valor', 'Categoria', 'Tipo', 'Situação', 'Data'])
    sheet.append(['Salário', 5000, 'Salário', 'Receita', 'Pago', '2026-03-10'])

    stream = io.BytesIO()
    try:
        workbook.save(stream)
    finally:
        workbook.close()
    stream.seek(0)

    uploaded = FileStorage(stream=stream, filename='finances.xlsx')
    result = import_finances_from_file(uploaded, user_id=1)

    assert result.imported_rows == 1
    assert result.entries[0].description == 'Salário'
    assert result.entries[0].type == 'Receita'


def test_import_finances_from_xlsx_supports_english_aliases():
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(['description', 'value', 'category', 'type', 'status', 'date'])
    sheet.append(['Salary', 5000, 'Salário', 'Income', 'Paid', '2026-03-10'])

    stream = io.BytesIO()
    try:
        workbook.save(stream)
    finally:
        workbook.close()
    stream.seek(0)

    uploaded = FileStorage(stream=stream, filename='finances.xlsx')
    result = import_finances_from_file(uploaded, user_id=1)

    assert result.imported_rows == 1
    assert result.entries[0].description == 'Salary'
    assert result.entries[0].type == 'Receita'
    assert result.entries[0].status == 'Pago'


def test_import_finances_rejects_unsupported_extension():
    uploaded = FileStorage(stream=io.BytesIO(b'test'), filename='finances.txt')

    with pytest.raises(ImportValidationError):
        import_finances_from_file(uploaded, user_id=1)


def test_import_finances_rejects_file_above_row_limit():
    csv_content = (
        'descricao,valor,categoria,tipo,status,data\n'
        'Item 1,10,Lazer,Despesa,Pago,2026-03-10\n'
        'Item 2,20,Lazer,Despesa,Pago,2026-03-11\n'
    )
    uploaded = FileStorage(stream=io.BytesIO(csv_content.encode('utf-8')), filename='finances.csv')

    with pytest.raises(ImportValidationError, match='limite de 1 linha permitida'):
        import_finances_from_file(uploaded, user_id=1, max_rows=1)


def test_import_finances_rejects_when_no_valid_entries_exist():
    # This file contains only an invalid row because imports require values > 0.
    csv_content = (
        'descricao,valor,categoria,tipo,status,data\n'
        'Item inválido,0,Lazer,Despesa,Pago,2026-03-10\n'
    )
    uploaded = FileStorage(stream=io.BytesIO(csv_content.encode('utf-8')), filename='finances.csv')

    with pytest.raises(ImportValidationError):
        import_finances_from_file(uploaded, user_id=1)


def test_import_finances_rejects_negative_values():
    csv_content = (
        'descricao,valor,categoria,tipo,status,data\n'
        'Item inválido,-10,Lazer,Despesa,Pago,2026-03-10\n'
    )
    uploaded = FileStorage(stream=io.BytesIO(csv_content.encode('utf-8')), filename='finances.csv')

    with pytest.raises(ImportValidationError, match='Valor deve ser maior que zero'):
        import_finances_from_file(uploaded, user_id=1)


def test_import_finances_rejects_zero_value():
    csv_content = (
        'descricao,valor,categoria,tipo,status,data\n'
        'Item zero,0,Lazer,Despesa,Pago,2026-03-10\n'
    )
    uploaded = FileStorage(stream=io.BytesIO(csv_content.encode('utf-8')), filename='finances.csv')

    with pytest.raises(ImportValidationError, match='Valor deve ser maior que zero'):
        import_finances_from_file(uploaded, user_id=1)


def test_import_finances_accepts_decimal_values():
    csv_content = (
        'descricao,valor,categoria,tipo,status,data\n'
        'Freela,10.75,Salário,Receita,Pago,2026-03-10\n'
    )
    uploaded = FileStorage(stream=io.BytesIO(csv_content.encode('utf-8')), filename='finances.csv')

    result = import_finances_from_file(uploaded, user_id=1)

    assert result.imported_rows == 1
    assert result.entries[0].value == 10.75
