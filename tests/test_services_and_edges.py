import io

import pytest
from PIL import Image
from sqlalchemy.exc import IntegrityError
from werkzeug.datastructures import FileStorage, MultiDict

from database.db import db
from models.user import User
from routes import imports as imports_module
from services import profile_service, recurring_service
from services import maintenance_service
from services.profile_service import (
    apply_profile_update,
    change_user_password,
    delete_user_account,
    parse_session_timeout_minutes,
)
from services.validators import parse_finance_form, validate_finance_data


def test_parse_finance_form_rejects_invalid_payment_date():
    payload, errors = parse_finance_form(
        MultiDict(
            {
                'description': 'Teste',
                'value': '10',
                'category': 'Lazer',
                'type': 'Despesa',
                'status': 'Pago',
                'due_date': '2026-03-10',
                'payment_date': '10-03-2026',
            }
        )
    )

    assert payload is None
    assert errors == ['Data de pagamento inválida.']


def test_parse_session_timeout_minutes_rejects_invalid_value():
    with pytest.raises(ValueError):
        parse_session_timeout_minutes('999')


def test_parse_session_timeout_minutes_accepts_valid_value():
    assert parse_session_timeout_minutes('15') == 15


def test_apply_profile_update_rejects_large_or_invalid_image(tmp_path, app):
    with app.app_context():
        user = User(username='imguser', email='img@example.com', name='Image User')
        user.set_password('Password123')
        db.session.add(user)
        db.session.commit()

        oversized = FileStorage(
            stream=io.BytesIO(b'a' * (2 * 1024 * 1024 + 1)),
            filename='avatar.png',
        )
        error_code = apply_profile_update(
            user=user,
            form=MultiDict({'name': 'Image User', 'email': 'img@example.com', 'session_timeout_minutes': '0'}),
            files={'profile_image': oversized},
            root_path=str(tmp_path),
            max_image_size=2 * 1024 * 1024,
        )
        assert error_code == 'image_too_large'

        invalid_image = FileStorage(
            stream=io.BytesIO(b'not-an-image'),
            filename='avatar.png',
        )
        error_code = apply_profile_update(
            user=user,
            form=MultiDict({'name': 'Image User', 'email': 'img@example.com', 'session_timeout_minutes': '0'}),
            files={'profile_image': invalid_image},
            root_path=str(tmp_path),
            max_image_size=2 * 1024 * 1024,
        )
        assert error_code == 'invalid_image'


def test_apply_profile_update_rejects_invalid_timeout_email_duplicate_and_image_name(tmp_path, app, monkeypatch):
    with app.app_context():
        primary = User(username='primary', email='primary@example.com', name='Primary')
        primary.set_password('Password123')
        duplicate = User(username='duplicate', email='duplicate@example.com', name='Duplicate')
        duplicate.set_password('Password123')
        db.session.add_all([primary, duplicate])
        db.session.commit()

        invalid_timeout = apply_profile_update(
            user=primary,
            form=MultiDict({'name': 'Primary', 'email': 'primary@example.com', 'session_timeout_minutes': '999'}),
            files={},
            root_path=str(tmp_path),
            max_image_size=1024,
        )
        assert invalid_timeout == 'invalid_session_timeout'

        invalid_email = apply_profile_update(
            user=primary,
            form=MultiDict({'name': 'Primary', 'email': 'not-an-email', 'session_timeout_minutes': '0'}),
            files={},
            root_path=str(tmp_path),
            max_image_size=1024,
        )
        assert invalid_email == 'invalid_email'

        duplicate_email = apply_profile_update(
            user=primary,
            form=MultiDict({'name': 'Primary', 'email': 'duplicate@example.com', 'session_timeout_minutes': '0'}),
            files={},
            root_path=str(tmp_path),
            max_image_size=1024,
        )
        assert duplicate_email == 'duplicate_email'

        image_buffer = io.BytesIO()
        Image.new('RGB', (1, 1), color='white').save(image_buffer, format='PNG')
        image_buffer.seek(0)
        monkeypatch.setattr(profile_service, 'secure_filename', lambda _name: '')
        invalid_name = apply_profile_update(
            user=primary,
            form=MultiDict({'name': 'Primary', 'email': 'primary@example.com', 'session_timeout_minutes': '0'}),
            files={'profile_image': FileStorage(stream=image_buffer, filename='avatar.png')},
            root_path=str(tmp_path),
            max_image_size=1024 * 1024,
        )
        assert invalid_name == 'invalid_image_name'


def test_apply_profile_update_handles_persist_failure(tmp_path, app, monkeypatch):
    with app.app_context():
        user = User(username='persistuser', email='persist@example.com', name='Persist')
        user.set_password('Password123')
        db.session.add(user)
        db.session.commit()

        monkeypatch.setattr(
            db.session,
            'commit',
            lambda: (_ for _ in ()).throw(IntegrityError('stmt', 'params', 'orig')),
        )
        error_code = apply_profile_update(
            user=user,
            form=MultiDict({'name': 'Persist', 'email': 'persist@example.com', 'session_timeout_minutes': '0'}),
            files={},
            root_path=str(tmp_path),
            max_image_size=1024,
        )
        assert error_code == 'profile_persist_failed'


def test_change_user_password_validates_current_and_strength(app):
    with app.app_context():
        user = User(username='pwduser', email='pwd@example.com', name='Pwd User')
        user.set_password('Password123')
        db.session.add(user)
        db.session.commit()

        assert change_user_password(user, 'wrong', 'NewPassword123') == 'invalid_current_password'
        assert change_user_password(user, 'Password123', 'weak') == 'weak_password'


def test_change_user_password_handles_commit_failure(app, monkeypatch):
    with app.app_context():
        user = User(username='pwdfail', email='pwdfail@example.com', name='Pwd Fail')
        user.set_password('Password123')
        db.session.add(user)
        db.session.commit()

        monkeypatch.setattr(
            db.session,
            'commit',
            lambda: (_ for _ in ()).throw(RuntimeError('boom')),
        )
        assert change_user_password(user, 'Password123', 'NewPassword123') == 'password_update_failed'


def test_delete_user_account_removes_user(app, tmp_path):
    with app.app_context():
        user = User(username='removeuser', email='remove@example.com', name='Remove User')
        user.set_password('Password123')
        db.session.add(user)
        db.session.commit()
        user_id = user.id

        error_code = delete_user_account(user, str(tmp_path))

        assert error_code is None
        assert db.session.get(User, user_id) is None


def test_delete_user_account_handles_commit_failure(app, tmp_path, monkeypatch):
    with app.app_context():
        user = User(username='deletefail', email='deletefail@example.com', name='Delete Fail')
        user.set_password('Password123')
        db.session.add(user)
        db.session.commit()

        monkeypatch.setattr(
            db.session,
            'commit',
            lambda: (_ for _ in ()).throw(RuntimeError('boom')),
        )
        assert delete_user_account(user, str(tmp_path)) == 'delete_account_failed'


def test_import_route_validates_missing_file(auth_client):
    response = auth_client.post('/import', data={}, follow_redirects=True)

    assert response.status_code == 200
    assert b'Nenhum arquivo foi enviado' in response.data


def test_import_route_validates_empty_filename(auth_client):
    response = auth_client.post(
        '/import',
        data={'file': (io.BytesIO(b''), '')},
        content_type='multipart/form-data',
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b'Selecione um arquivo antes de importar' in response.data


def test_import_route_handles_unexpected_errors(auth_client, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError('boom')

    monkeypatch.setattr(imports_module, 'import_finances_from_file', boom)
    response = auth_client.post(
        '/import',
        data={'file': (io.BytesIO(b'data'), 'finances.csv')},
        content_type='multipart/form-data',
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b'Erro inesperado ao importar arquivo' in response.data


def test_start_recurring_scheduler_starts_worker_when_enabled(monkeypatch):
    calls = {'maintenance': 0, 'thread_started': 0}

    class FakeEvent:
        def __init__(self):
            self.wait_calls = 0

        def wait(self, _interval):
            self.wait_calls += 1
            return self.wait_calls > 1

    class FakeThread:
        def __init__(self, target, name, daemon):
            self.target = target
            self.name = name
            self.daemon = daemon

        def start(self):
            calls['thread_started'] += 1
            self.target()

    class FakeLogger:
        def exception(self, *_args, **_kwargs):
            raise AssertionError('scheduler should not log exceptions in this test')

    class FakeApp:
        config = {
            'TESTING': False,
            'ENABLE_RECURRING_SCHEDULER': True,
            'RECURRING_PROCESS_INTERVAL_SECONDS': 60,
        }
        logger = FakeLogger()

    monkeypatch.setattr(maintenance_service.threading, 'Event', FakeEvent)
    monkeypatch.setattr(maintenance_service.threading, 'Thread', FakeThread)
    monkeypatch.setattr(
        maintenance_service,
        'run_recurring_maintenance',
        lambda app: calls.__setitem__('maintenance', calls['maintenance'] + 1),
    )

    stop_event = maintenance_service.start_recurring_scheduler(FakeApp())

    assert stop_event is not None
    assert calls['thread_started'] == 1
    assert calls['maintenance'] == 1


def test_validate_finance_data_covers_length_and_type_rules():
    errors = validate_finance_data(
        MultiDict(
            {
                'description': 'x' * 101,
                'value': '-1',
                'category': 'y' * 51,
                'type': 'Outro',
                'status': 'Desconhecido',
                'due_date': '',
            }
        )
    )

    assert 'Descrição deve ter no máximo 100 caracteres.' in errors
    assert 'Categoria deve ter no máximo 50 caracteres.' in errors
    assert 'Tipo de lançamento inválido.' in errors
    assert 'Status de lançamento inválido.' in errors


def test_parse_finance_form_returns_normalized_payload():
    payload, errors = parse_finance_form(
        MultiDict(
            {
                'description': '  Compra  ',
                'value': '10.50',
                'category': ' Lazer ',
                'type': 'Despesa',
                'status': 'Pago',
                'due_date': '2026-03-10',
                'payment_date': '2026-03-11',
                'observations': '  observacao  ',
            }
        )
    )

    assert errors == []
    assert payload['description'] == 'Compra'
    assert payload['category'] == 'Lazer'
    assert payload['observations'] == 'observacao'


def test_get_next_run_date_supports_all_frequencies():
    from datetime import date

    base = date(2026, 3, 10)
    assert recurring_service.get_next_run_date(base, 'Diário').day == 11
    assert recurring_service.get_next_run_date(base, 'Semanal').day == 17
    assert recurring_service.get_next_run_date(base, 'Mensal').month == 4
    assert recurring_service.get_next_run_date(base, 'Anual').year == 2027
    assert recurring_service.get_next_run_date(base, 'Invalida') is None
