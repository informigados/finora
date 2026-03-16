import io
from pathlib import Path

from PIL import Image
from itsdangerous import URLSafeTimedSerializer
from werkzeug.datastructures import FileStorage

import app as app_module
from app import (
    ensure_runtime_schema_compatibility,
    ensure_sqlite_schema_bootstrapped,
    ensure_sqlite_schema_up_to_date,
)
from database.db import db
from models.goal import Goal
from models.user import User
from services import auth_service, profile_service


def _create_user(app, username, email, password='Password123'):
    with app.app_context():
        user = User(username=username, email=email, name=username.title())
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        return user.id


def _login(client, username, password='Password123'):
    return client.post(
        '/login',
        data={'identifier': username, 'password': password},
        follow_redirects=True,
    )


def test_resolve_reset_token_rejects_missing_payload_fields(app):
    with app.app_context():
        serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'], salt='finora-reset-password')
        missing_email_token = serializer.dumps({'user_id': 1})
        missing_user_token = serializer.dumps({'email': 'user@example.com'})

        assert auth_service.resolve_user_from_reset_token(missing_email_token) == (None, 'invalid')
        assert auth_service.resolve_user_from_reset_token(missing_user_token) == (None, 'invalid')


def test_profile_service_uses_remote_addr_when_proxy_headers_are_not_trusted(app):
    with app.test_request_context(
        '/',
        headers={'X-Forwarded-For': '203.0.113.5'},
        environ_base={'REMOTE_ADDR': '127.0.0.1'},
    ):
        app.config['TRUST_PROXY_HEADERS'] = False
        assert profile_service._request_ip_address(app_module.request) == '127.0.0.1'


def test_profile_service_can_trust_forwarded_ip_when_enabled(app):
    with app.test_request_context(
        '/',
        headers={'X-Forwarded-For': '203.0.113.5, 10.0.0.1'},
        environ_base={'REMOTE_ADDR': '127.0.0.1'},
    ):
        app.config['TRUST_PROXY_HEADERS'] = True
        assert profile_service._request_ip_address(app_module.request) == '203.0.113.5'


def test_ensure_user_session_reuses_recent_session_with_same_client_fingerprint(app):
    with app.app_context():
        user = User(username='sessionreuse', email='sessionreuse@example.com', name='Session Reuse')
        user.set_password('Password123')
        db.session.add(user)
        db.session.commit()

        existing_session = profile_service.UserSession(
            user_id=user.id,
            session_token_hash='existing-hash',
            ip_address='127.0.0.1',
            user_agent='pytest-agent',
            started_at=profile_service.utcnow_naive(),
            last_seen_at=profile_service.utcnow_naive(),
            is_current=True,
        )
        db.session.add(existing_session)
        db.session.commit()

        session_store = {}
        with app.test_request_context('/', headers={'User-Agent': 'pytest-agent'}, environ_base={'REMOTE_ADDR': '127.0.0.1'}):
            reused = profile_service.ensure_user_session(user, app_module.request, session_store)

        assert reused is not None
        assert reused.id == existing_session.id
        assert 'audit_session_token' not in session_store
        assert session_store['audit_session_id'] == existing_session.id
        assert profile_service.UserSession.query.filter_by(user_id=user.id, is_current=True).count() == 1


def test_resolve_reset_token_rejects_email_mismatch_and_unknown_user(app):
    with app.app_context():
        user = User(username='tokenmismatch', email='tokenmismatch@example.com', name='Token Mismatch')
        user.set_password('Password123')
        db.session.add(user)
        db.session.commit()

        serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'], salt='finora-reset-password')
        mismatch_token = serializer.dumps({'user_id': user.id, 'email': 'other@example.com'})
        unknown_user_token = serializer.dumps({'user_id': user.id + 999, 'email': 'ghost@example.com'})

        assert auth_service.resolve_user_from_reset_token(mismatch_token) == (None, 'invalid')
        assert auth_service.resolve_user_from_reset_token(unknown_user_token) == (None, 'invalid')


def test_find_user_by_identifier_and_commit_auth_security_state(app, monkeypatch):
    with app.app_context():
        user = User(username='lookuphelper', email='lookuphelper@example.com', name='Lookup Helper')
        user.set_password('Password123')
        db.session.add(user)
        db.session.commit()

        assert auth_service.find_user_by_identifier(' lookuphelper ') is not None
        assert auth_service.find_user_by_identifier('LOOKUPHELPER@example.com') is not None
        assert auth_service.find_user_by_identifier('') is None

        calls = {'rollback': 0}
        monkeypatch.setattr(db.session, 'commit', lambda: (_ for _ in ()).throw(RuntimeError('boom')))
        monkeypatch.setattr(db.session, 'rollback', lambda: calls.__setitem__('rollback', calls['rollback'] + 1))

        auth_service.commit_auth_security_state()

        assert calls['rollback'] == 1


def test_profile_service_file_helpers(tmp_path):
    image_buffer = io.BytesIO()
    Image.new('RGB', (2, 2), color='white').save(image_buffer, format='PNG')
    image_buffer.seek(0)

    upload = FileStorage(stream=image_buffer, filename='avatar.png')
    assert profile_service.uploaded_file_size(upload) > 0

    image_buffer.seek(0)
    assert profile_service.is_valid_image(image_buffer) is True

    invalid_buffer = io.BytesIO(b'not-an-image')
    assert profile_service.is_valid_image(invalid_buffer) is False

    custom_dir = tmp_path / 'static' / 'profile_pics'
    custom_dir.mkdir(parents=True, exist_ok=True)
    custom_file = custom_dir / 'custom.png'
    custom_file.write_bytes(b'test')

    profile_service.remove_profile_image_if_custom(str(tmp_path), 'custom.png')
    assert not custom_file.exists()

    profile_service.remove_profile_image_if_custom(str(tmp_path), profile_service.DEFAULT_PROFILE_IMAGE)


def test_runtime_schema_compatibility_applies_missing_columns(app, monkeypatch):
    app.config['TESTING'] = False
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///runtime.db'

    executed = []
    committed = {'count': 0}

    class FakeInspector:
        def get_table_names(self):
            return ['user']

        def get_columns(self, _table_name):
            return [{'name': 'session_timeout_minutes'}]

    monkeypatch.setattr(app_module, 'inspect', lambda _engine: FakeInspector())
    monkeypatch.setattr(db.session, 'execute', lambda statement: executed.append(str(statement)))
    monkeypatch.setattr(db.session, 'commit', lambda: committed.__setitem__('count', committed['count'] + 1))

    ensure_runtime_schema_compatibility(app)

    assert any('failed_login_attempts' in statement for statement in executed)
    assert any('locked_until' in statement for statement in executed)
    assert committed['count'] == 2


def test_runtime_schema_compatibility_skips_alembic_managed_sqlite(app, monkeypatch):
    app.config['TESTING'] = False
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///runtime.db'

    class FakeInspector:
        def get_table_names(self):
            return ['alembic_version', 'user']

        def get_columns(self, _table_name):
            return []

    monkeypatch.setattr(app_module, 'inspect', lambda _engine: FakeInspector())
    monkeypatch.setattr(
        db.session,
        'execute',
        lambda _statement: (_ for _ in ()).throw(AssertionError('runtime patch should be skipped')),
    )

    ensure_runtime_schema_compatibility(app)


def test_runtime_schema_compatibility_rolls_back_on_failure(app, monkeypatch):
    app.config['TESTING'] = False
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///runtime.db'

    class FakeInspector:
        def get_table_names(self):
            return ['user']

        def get_columns(self, _table_name):
            return []

    calls = {'rollback': 0}
    monkeypatch.setattr(app_module, 'inspect', lambda _engine: FakeInspector())
    monkeypatch.setattr(db.session, 'execute', lambda _statement: (_ for _ in ()).throw(RuntimeError('boom')))
    monkeypatch.setattr(db.session, 'rollback', lambda: calls.__setitem__('rollback', calls['rollback'] + 1))

    ensure_runtime_schema_compatibility(app)

    assert calls['rollback'] == 1


def test_ensure_sqlite_schema_bootstrapped_repairs_alembic_only_database(app, monkeypatch, tmp_path):
    app.config['TESTING'] = False
    app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{(tmp_path / 'broken.db').as_posix()}"
    db_path = Path(tmp_path) / 'broken.db'
    db_path.write_text('placeholder', encoding='utf-8')

    inspections = iter([
        {'alembic_version'},
        {'alembic_version', 'user', 'finances', 'goals', 'budgets', 'recurring_entries'},
    ])
    backups = []

    class FakeInspector:
        def __init__(self, table_names):
            self._table_names = table_names

        def get_table_names(self):
            return list(self._table_names)

    monkeypatch.setattr(
        app_module,
        'inspect',
        lambda _engine: FakeInspector(next(inspections)),
    )
    monkeypatch.setattr(app_module.db.session, 'remove', lambda: None)
    monkeypatch.setattr(app_module.db.engine, 'dispose', lambda: None)
    monkeypatch.setattr(
        app_module.shutil,
        'copy2',
        lambda src, dst: backups.append((src, dst)),
    )
    monkeypatch.setattr(app_module.os, 'remove', lambda _path: None)
    create_all_calls = {'count': 0}
    stamp_calls = {'count': 0}
    monkeypatch.setattr(app_module.db, 'create_all', lambda: create_all_calls.__setitem__('count', create_all_calls['count'] + 1))
    monkeypatch.setattr(
        app_module,
        '_stamp_alembic_head',
        lambda _app: stamp_calls.__setitem__('count', stamp_calls['count'] + 1),
    )

    ensure_sqlite_schema_bootstrapped(app)

    assert create_all_calls['count'] == 1
    assert stamp_calls['count'] == 1
    assert backups
    assert Path(backups[0][0]) == db_path


def test_ensure_sqlite_schema_bootstrapped_creates_empty_database_without_backup(app, monkeypatch, tmp_path):
    app.config['TESTING'] = False
    app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{(tmp_path / 'empty.db').as_posix()}"
    db_path = Path(tmp_path) / 'empty.db'
    db_path.write_text('', encoding='utf-8')

    inspections = iter([
        set(),
        {'alembic_version', 'user', 'finances', 'goals', 'budgets', 'recurring_entries'},
    ])
    backup_calls = {'count': 0}
    remove_calls = {'count': 0}

    class FakeInspector:
        def __init__(self, table_names):
            self._table_names = table_names

        def get_table_names(self):
            return list(self._table_names)

    monkeypatch.setattr(app_module, 'inspect', lambda _engine: FakeInspector(next(inspections)))
    monkeypatch.setattr(app_module.db.session, 'remove', lambda: None)
    monkeypatch.setattr(app_module.db.engine, 'dispose', lambda: None)
    monkeypatch.setattr(
        app_module.shutil,
        'copy2',
        lambda *_args, **_kwargs: backup_calls.__setitem__('count', backup_calls['count'] + 1),
    )
    monkeypatch.setattr(
        app_module.os,
        'remove',
        lambda *_args, **_kwargs: remove_calls.__setitem__('count', remove_calls['count'] + 1),
    )
    create_all_calls = {'count': 0}
    stamp_calls = {'count': 0}
    monkeypatch.setattr(app_module.db, 'create_all', lambda: create_all_calls.__setitem__('count', create_all_calls['count'] + 1))
    monkeypatch.setattr(
        app_module,
        '_stamp_alembic_head',
        lambda _app: stamp_calls.__setitem__('count', stamp_calls['count'] + 1),
    )

    ensure_sqlite_schema_bootstrapped(app)

    assert create_all_calls['count'] == 1
    assert stamp_calls['count'] == 1
    assert backup_calls['count'] == 0
    assert remove_calls['count'] == 0


def test_ensure_sqlite_schema_up_to_date_runs_pending_migrations(app, monkeypatch, tmp_path):
    app.config['TESTING'] = False
    app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{(tmp_path / 'stale.db').as_posix()}"

    class FakeInspector:
        def get_table_names(self):
            return ['alembic_version', 'user']

    upgrade_calls = {'count': 0}
    dispose_calls = {'count': 0}
    remove_calls = {'count': 0}

    monkeypatch.setattr(app_module, 'inspect', lambda _engine: FakeInspector())
    monkeypatch.setattr(
        db.session,
        'execute',
        lambda _statement: type('Result', (), {'scalar': lambda self: 'd3a7f9c2b4e1'})(),
    )
    monkeypatch.setattr(app_module, '_get_alembic_head_revision', lambda _app: 'e4c9b7f1a2d3')
    monkeypatch.setattr(
        app_module.alembic_command,
        'upgrade',
        lambda *_args, **_kwargs: upgrade_calls.__setitem__('count', upgrade_calls['count'] + 1),
    )
    monkeypatch.setattr(app_module.db.session, 'remove', lambda: remove_calls.__setitem__('count', remove_calls['count'] + 1))
    monkeypatch.setattr(app_module.db.engine, 'dispose', lambda: dispose_calls.__setitem__('count', dispose_calls['count'] + 1))

    ensure_sqlite_schema_up_to_date(app)

    assert upgrade_calls['count'] == 1
    assert remove_calls['count'] >= 1
    assert dispose_calls['count'] == 1


def test_ensure_sqlite_schema_up_to_date_skips_when_revision_is_current(app, monkeypatch, tmp_path):
    app.config['TESTING'] = False
    app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{(tmp_path / 'current.db').as_posix()}"

    class FakeInspector:
        def get_table_names(self):
            return ['alembic_version', 'user']

    monkeypatch.setattr(app_module, 'inspect', lambda _engine: FakeInspector())
    monkeypatch.setattr(
        db.session,
        'execute',
        lambda _statement: type('Result', (), {'scalar': lambda self: 'e4c9b7f1a2d3'})(),
    )
    monkeypatch.setattr(app_module, '_get_alembic_head_revision', lambda _app: 'e4c9b7f1a2d3')
    monkeypatch.setattr(
        app_module.alembic_command,
        'upgrade',
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError('upgrade should be skipped')),
    )

    ensure_sqlite_schema_up_to_date(app)


def test_seed_default_user_handles_unexpected_failure(app, monkeypatch):
    with app.app_context():
        db.create_all()
        app.config['TESTING'] = False
        app.config['ENABLE_DEFAULT_USER_SEED'] = True
        monkeypatch.setenv('DEFAULT_USER_PASSWORD', 'SeedPassword123')
        monkeypatch.setattr(User.query, 'filter_by', lambda **_kwargs: (_ for _ in ()).throw(RuntimeError('boom')))

        seed_error = None
        try:
            app_module.seed_default_user(app)
        except Exception as exc:  # pragma: no cover
            seed_error = exc

        assert seed_error is None


def test_goal_delete_ignores_foreign_goal(client, app):
    _create_user(app, 'goalownerforeign', 'goalownerforeign@example.com')
    other_id = _create_user(app, 'goalotherforeign', 'goalotherforeign@example.com')
    with app.app_context():
        goal = Goal(name='Goal Foreign', target_amount=1000.0, current_amount=200.0, user_id=other_id)
        db.session.add(goal)
        db.session.commit()
        goal_id = goal.id

    _login(client, 'goalownerforeign')
    response = client.post(f'/goals/delete/{goal_id}', follow_redirects=False)

    assert response.status_code == 302
    with app.app_context():
        assert db.session.get(Goal, goal_id) is not None
