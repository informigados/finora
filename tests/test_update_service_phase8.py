import json
import os
import zipfile

import pytest

from database.db import db
from models.system import AppUpdateState
from models.user import User
from services import update_service


def _write_manifest(tmp_path, payload):
    manifest_path = tmp_path / 'manifest.json'
    manifest_path.write_text(json.dumps(payload), encoding='utf-8')
    return manifest_path


def _build_update_package(tmp_path, files_by_name):
    package_root = tmp_path / 'package_root'
    package_root.mkdir()
    for relative_name, content in files_by_name.items():
        target_path = package_root / relative_name
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(content, encoding='utf-8')

    package_path = tmp_path / 'finora-update.zip'
    with zipfile.ZipFile(package_path, 'w', zipfile.ZIP_DEFLATED) as archive:
        for file_path in package_root.rglob('*'):
            if file_path.is_file():
                archive.write(file_path, file_path.relative_to(package_root))
    return package_path


def _prepare_target_root(tmp_path):
    target_root = tmp_path / 'target_app'
    (target_root / 'routes').mkdir(parents=True)
    (target_root / 'templates').mkdir(parents=True)
    (target_root / 'database').mkdir(parents=True)
    (target_root / 'app.py').write_text('VERSION = "old"\n', encoding='utf-8')
    (target_root / 'routes' / '__init__.py').write_text('', encoding='utf-8')
    (target_root / 'templates' / 'about.html').write_text('old about', encoding='utf-8')
    (target_root / 'database' / 'keep.txt').write_text('keep-me', encoding='utf-8')
    return target_root


def test_check_for_updates_marks_state_as_available_when_newer_version_in_manifest(app, tmp_path):
    unused_package = tmp_path / 'unused.zip'
    unused_package.write_bytes(b'PK')
    manifest_path = _write_manifest(
        tmp_path,
        {
            'channels': {
                'stable': {
                    'version': '1.3.1',
                    'asset_url': str(unused_package),
                    'requires_migration': True,
                }
            }
        },
    )
    app.config['UPDATE_MANIFEST_URL'] = str(manifest_path)
    app.config['UPDATE_ALLOW_LOCAL_ASSETS'] = True
    app.config['APP_VERSION'] = '1.3.0'

    with app.app_context():
        result = update_service.check_for_updates(app)
        state = result['state']

        assert result['update_available'] is True
        assert state.status == 'available'
        assert state.installed_version == '1.3.0'
        assert state.latest_known_version == '1.3.1'
        assert state.last_checked_at is not None


def test_apply_update_installs_package_and_preserves_excluded_directories(app, tmp_path, monkeypatch):
    target_root = _prepare_target_root(tmp_path)
    package_path = _build_update_package(
        tmp_path,
        {
            'app.py': 'VERSION = "new"\n',
            'routes/__init__.py': '',
            'templates/about.html': 'new about',
            'database/keep.txt': 'should-not-overwrite',
        },
    )
    manifest_path = _write_manifest(
        tmp_path,
        {
            'version': '1.3.1',
            'asset_url': str(package_path),
            'requires_migration': True,
        },
    )

    migration_calls = []

    def fake_run_database_upgrade(_app):
        migration_calls.append(True)

    monkeypatch.setattr(update_service, '_run_database_upgrade', fake_run_database_upgrade)

    app.config['UPDATE_MANIFEST_URL'] = str(manifest_path)
    app.config['UPDATE_TARGET_ROOT'] = str(target_root)
    app.config['UPDATE_DOWNLOAD_DIR'] = str(tmp_path / 'updates')
    app.config['UPDATE_ALLOW_LOCAL_ASSETS'] = True
    app.config['APP_VERSION'] = '1.3.0'

    with app.app_context():
        user = User(username='updater', email='updater@example.com', name='Updater')
        user.set_password('Password123')
        db.session.add(user)
        db.session.commit()

        result = update_service.apply_update(app, user=user)
        state = AppUpdateState.query.first()

        assert result['applied'] is True
        assert migration_calls == [True]
        assert state.installed_version == '1.3.1'
        assert state.status == 'applied'
        assert os.path.exists(result['backup_path'])
        assert os.path.exists(result['package_path'])

    assert (target_root / 'app.py').read_text(encoding='utf-8') == 'VERSION = "new"\n'
    assert (target_root / 'templates' / 'about.html').read_text(encoding='utf-8') == 'new about'
    assert (target_root / 'database' / 'keep.txt').read_text(encoding='utf-8') == 'keep-me'


def test_apply_update_restores_backup_when_upgrade_fails(app, tmp_path, monkeypatch):
    target_root = _prepare_target_root(tmp_path)
    package_path = _build_update_package(
        tmp_path,
        {
            'app.py': 'VERSION = "broken"\n',
            'routes/__init__.py': '',
            'templates/about.html': 'broken about',
        },
    )
    manifest_path = _write_manifest(
        tmp_path,
        {
            'version': '1.3.1',
            'asset_url': str(package_path),
            'requires_migration': True,
        },
    )

    monkeypatch.setattr(
        update_service,
        '_run_database_upgrade',
        lambda _app: (_ for _ in ()).throw(RuntimeError('migration failed')),
    )

    app.config['UPDATE_MANIFEST_URL'] = str(manifest_path)
    app.config['UPDATE_TARGET_ROOT'] = str(target_root)
    app.config['UPDATE_DOWNLOAD_DIR'] = str(tmp_path / 'updates')
    app.config['UPDATE_ALLOW_LOCAL_ASSETS'] = True
    app.config['APP_VERSION'] = '1.3.0'

    with app.app_context():
        with pytest.raises(RuntimeError, match='migration failed'):
            update_service.apply_update(app)

        state = AppUpdateState.query.first()
        assert state.status == 'error'
        assert 'migration failed' in (state.last_error or '')

    assert (target_root / 'app.py').read_text(encoding='utf-8') == 'VERSION = "old"\n'
    assert (target_root / 'templates' / 'about.html').read_text(encoding='utf-8') == 'old about'


def test_about_routes_expose_update_section_and_check_flow(client, app, tmp_path):
    unused_package = tmp_path / 'unused.zip'
    unused_package.write_bytes(b'PK')
    manifest_path = _write_manifest(
        tmp_path,
        {
            'version': '1.3.1',
            'asset_url': str(unused_package),
            'requires_migration': True,
        },
    )
    app.config['UPDATE_MANIFEST_URL'] = str(manifest_path)
    app.config['UPDATE_ALLOW_LOCAL_ASSETS'] = True
    app.config['APP_VERSION'] = '1.3.0'

    with app.app_context():
        user = User(username='aboutupdater', email='aboutupdater@example.com', name='About Updater')
        user.set_password('Password123')
        db.session.add(user)
        db.session.commit()

    response = client.get('/about')
    assert response.status_code == 200
    assert b'Atualiza' in response.data
    assert b'Vers' in response.data
    assert b'name="csrf_token"' in response.data
    assert b'manifesto local padr' in response.data

    check_response = client.post('/about/check-update', follow_redirects=True)
    assert check_response.status_code == 200
    assert b'Nova vers' in check_response.data

    apply_requires_login = client.post('/about/apply-update', follow_redirects=False)
    assert apply_requires_login.status_code == 302
    assert '/login' in apply_requires_login.headers['Location']


def test_about_hides_update_error_details_from_public_users(client, app):
    with app.app_context():
        state = update_service.get_or_create_update_state(app)
        state.status = 'error'
        state.last_error = 'stacktrace: secret detail'
        db.session.commit()

    response = client.get('/about')

    assert response.status_code == 200
    assert b'Fa\xc3\xa7a login para ver os detalhes' in response.data
    assert b'secret detail' not in response.data


def test_about_shows_update_error_details_to_authenticated_users(client, app):
    with app.app_context():
        user = User(username='aboutdetail', email='aboutdetail@example.com', name='About Detail')
        user.set_password('Password123')
        db.session.add(user)
        db.session.commit()

        state = update_service.get_or_create_update_state(app)
        state.status = 'error'
        state.last_error = 'stacktrace: secret detail'
        db.session.commit()

    client.post('/login', data={'identifier': 'aboutdetail', 'password': 'Password123'}, follow_redirects=True)
    response = client.get('/about')

    assert response.status_code == 200
    assert b'secret detail' in response.data


def test_check_for_updates_uses_bundled_manifest_when_not_overridden(app):
    app.config['APP_VERSION'] = '1.3.0'
    app.config['UPDATE_CHANNEL'] = 'stable'

    with app.app_context():
        result = update_service.check_for_updates(app)
        overview = update_service.get_update_overview(app)

    assert result.get('error') is None
    assert result['manifest']['version'] == '1.3.0'
    assert result['update_available'] is False
    assert overview['update_configured'] is True
    assert overview['update_remote_configured'] is False


def test_check_for_updates_blocks_local_assets_from_local_manifest_by_default(app, tmp_path):
    package_path = tmp_path / 'blocked-update.zip'
    package_path.write_bytes(b'PK')
    manifest_path = _write_manifest(
        tmp_path,
        {
            'version': '1.3.1',
            'asset_url': str(package_path),
            'requires_migration': True,
        },
    )
    app.config['UPDATE_MANIFEST_URL'] = str(manifest_path)
    app.config['APP_VERSION'] = '1.3.0'
    app.config['UPDATE_ALLOW_LOCAL_ASSETS'] = False

    with app.app_context():
        result = update_service.check_for_updates(app)

    assert result['manifest']['asset_url'] == ''
    assert result['update_available'] is False
    assert result['state'].status == 'up_to_date'


def test_open_source_stream_rejects_remote_insecure_schemes(app):
    with app.app_context():
        with pytest.raises(ValueError, match='HTTPS'):
            stream = update_service._open_source_stream('http://example.com/update.json', 5)
            stream.close()

        with pytest.raises(ValueError, match='HTTPS'):
            stream = update_service._open_source_stream('file:///tmp/update.json', 5)
            stream.close()


def test_run_database_upgrade_uses_sanitized_environment(app, monkeypatch, tmp_path):
    captured = {}
    app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{(tmp_path / 'db.sqlite3').as_posix()}"
    app.config['UPDATE_TARGET_ROOT'] = str(tmp_path)
    app.config['SECRET_KEY'] = 'test-secret'
    monkeypatch.setenv('FLASK_APP', 'evil.py')
    monkeypatch.setenv('DATABASE_URL', 'sqlite:///wrong.db')

    def fake_run(command, **kwargs):
        captured['command'] = command
        captured['env'] = kwargs['env']

        class Result:
            returncode = 0
            stderr = ''
            stdout = ''

        return Result()

    monkeypatch.setattr(update_service.subprocess, 'run', fake_run)

    with app.app_context():
        update_service._run_database_upgrade(app)

    assert captured['command'] == [update_service.sys.executable, '-m', 'flask', 'db', 'upgrade']
    assert captured['env']['FLASK_APP'] == 'app.py'
    assert captured['env']['DATABASE_URL'] == app.config['SQLALCHEMY_DATABASE_URI']
    assert captured['env']['ENABLE_DEFAULT_USER_SEED'] == '0'
