import hashlib
import json
import os
import zipfile
from datetime import datetime
from types import SimpleNamespace

import pytest
from sqlalchemy.engine import make_url

from database.db import db
from models.user import User
from services import backup_service, update_service


def _build_target_root(tmp_path):
    target_root = tmp_path / 'target'
    (target_root / 'routes').mkdir(parents=True)
    (target_root / 'templates').mkdir(parents=True)
    (target_root / 'database').mkdir(parents=True)
    (target_root / 'logs').mkdir(parents=True)
    (target_root / 'app.py').write_text('VERSION = "old"\n', encoding='utf-8')
    (target_root / 'routes' / '__init__.py').write_text('', encoding='utf-8')
    (target_root / 'templates' / 'about.html').write_text('old about', encoding='utf-8')
    (target_root / 'database' / 'keep.txt').write_text('runtime', encoding='utf-8')
    (target_root / '.env').write_text('SECRET_KEY=test\n', encoding='utf-8')
    (target_root / 'logs' / 'app.log').write_text('ignore me\n', encoding='utf-8')
    return target_root


def test_update_service_version_helpers_and_channel_extraction():
    assert update_service.parse_version_tokens('v1.3.0-beta') == (
        (0, 1),
        (0, 3),
        (0, 0),
        (1, 'beta'),
    )
    assert update_service.compare_versions('1.3.1', '1.3.0') == 1
    assert update_service.compare_versions('1.3.0', '1.3.1') == -1
    assert update_service.compare_versions('1.3.0', '1.3.0') == 0
    assert update_service._extract_channel_payload(
        {'channels': {'stable': {'version': '1.3.1'}}},
        'stable',
    ) == {'version': '1.3.1'}
    assert update_service._extract_channel_payload({'version': '1.3.0'}, 'stable') == {
        'version': '1.3.0'
    }
    with pytest.raises(ValueError, match='Canal de atualização'):
        update_service._extract_channel_payload({'channels': {'beta': {}}}, 'stable')
    with pytest.raises(ValueError, match='Manifesto de atualização inválido'):
        update_service._extract_channel_payload([], 'stable')


def test_update_service_asset_filename_checksum_and_environment(app, tmp_path, monkeypatch):
    package_path = tmp_path / 'payload.bin'
    package_path.write_bytes(b'finora-update')

    assert update_service._derive_asset_filename('https://example.com/releases/build', '1.3.1') == (
        'build.zip'
    )
    assert update_service._derive_asset_filename('', '1.3.1') == 'finora_update_1.3.1.zip'
    assert update_service._calculate_sha256(str(package_path)) == hashlib.sha256(
        b'finora-update'
    ).hexdigest()

    monkeypatch.setenv('PATH', 'C:/Windows/System32')
    monkeypatch.setenv('DATABASE_URL', 'sqlite:///evil.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///good.db'
    app.config['SECRET_KEY'] = 'secret'
    app.config['APP_BASE_URL'] = 'https://finora.local'

    environment = update_service._build_upgrade_environment(app)

    assert environment['FLASK_APP'] == 'app.py'
    assert environment['FLASK_ENV'] == 'production'
    assert environment['DATABASE_URL'] == 'sqlite:///good.db'
    assert environment['SECRET_KEY'] == 'secret'
    assert environment['ENABLE_DEFAULT_USER_SEED'] == '0'
    assert environment['APP_BASE_URL'] == 'https://finora.local'
    assert environment['PATH'] == 'C:/Windows/System32'


def test_update_service_extract_detect_backup_restore_and_download(app, tmp_path):
    target_root = _build_target_root(tmp_path)
    app.config['UPDATE_TARGET_ROOT'] = str(target_root)
    app.config['UPDATE_DOWNLOAD_DIR'] = str(tmp_path / 'updates')
    app.config['UPDATE_CHECK_TIMEOUT_SECONDS'] = 5

    package_root = tmp_path / 'pkg'
    (package_root / 'finora-app' / 'routes').mkdir(parents=True)
    (package_root / 'finora-app' / 'templates').mkdir(parents=True)
    (package_root / 'finora-app' / 'app.py').write_text('VERSION = "new"\n', encoding='utf-8')
    (package_root / 'finora-app' / 'routes' / '__init__.py').write_text('', encoding='utf-8')
    (package_root / 'finora-app' / 'templates' / 'about.html').write_text('new about', encoding='utf-8')

    archive_path = tmp_path / 'update.zip'
    with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as archive:
        for file_path in (package_root / 'finora-app').rglob('*'):
            if file_path.is_file():
                archive.write(file_path, file_path.relative_to(package_root))

    extract_dir = tmp_path / 'extract'
    update_service._safe_extract_zip(str(archive_path), str(extract_dir))
    detected_root = update_service._detect_package_root(str(extract_dir))
    assert os.path.exists(os.path.join(detected_root, 'app.py'))

    backup_path = update_service._build_pre_update_backup(app, '1.3.0')
    with zipfile.ZipFile(backup_path, 'r') as archive:
        names = set(archive.namelist())
    assert 'app.py' in names
    assert 'database/keep.txt' in names
    assert '.env' not in names
    assert 'logs/app.log' not in names

    (target_root / 'app.py').write_text('VERSION = "broken"\n', encoding='utf-8')
    update_service._restore_pre_update_backup(str(target_root), backup_path)
    assert (target_root / 'app.py').read_text(encoding='utf-8') == 'VERSION = "old"\n'

    manifest = {
        'asset_url': str(archive_path),
        'version': '1.3.1',
        'sha256': update_service._calculate_sha256(str(archive_path)),
    }
    downloaded_path = update_service._download_update_asset(app, manifest)
    assert os.path.exists(downloaded_path)

    with pytest.raises(ValueError, match='Checksum'):
        update_service._download_update_asset(
            app,
            {
                'asset_url': str(archive_path),
                'version': '1.3.1',
                'sha256': 'deadbeef',
            },
        )


def test_update_service_safe_extract_and_detect_package_root_failures(tmp_path):
    invalid_archive = tmp_path / 'invalid.zip'
    with zipfile.ZipFile(invalid_archive, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('../escape.txt', 'boom')

    with pytest.raises(ValueError, match='caminho inválido'):
        update_service._safe_extract_zip(str(invalid_archive), str(tmp_path / 'extract'))

    empty_root = tmp_path / 'empty'
    empty_root.mkdir()
    with pytest.raises(ValueError, match='estrutura esperada'):
        update_service._detect_package_root(str(empty_root))


def test_backup_service_labels_schedule_math_and_schedule_creation(app):
    with app.app_context():
        user = User(username='backupuser', email='backupuser@example.com', name='Backup User')
        user.set_password('Password123')
        db.session.add(user)
        db.session.commit()

        schedule = backup_service.get_or_create_backup_schedule(user, 14)
        assert schedule.enabled is False
        assert schedule.retention_count == 14
        assert backup_service.get_or_create_backup_schedule(user, 7).id == schedule.id

    assert backup_service.get_backup_weekday_label(1) == 'Terça-feira'
    assert backup_service.get_backup_weekday_label(99) is None

    disabled_schedule = SimpleNamespace(enabled=False)
    assert backup_service.calculate_next_backup_run(disabled_schedule) is None

    daily_schedule = SimpleNamespace(
        enabled=True,
        frequency='Diário',
        times_per_period=2,
        run_hour=6,
        run_minute=0,
        day_of_week=None,
        day_of_month=None,
    )
    daily_next = backup_service.calculate_next_backup_run(
        daily_schedule,
        from_dt=datetime(2026, 3, 16, 8, 0),
    )
    assert daily_next == datetime(2026, 3, 16, 18, 0)

    weekly_schedule = SimpleNamespace(
        enabled=True,
        frequency='Semanal',
        times_per_period=1,
        day_of_week=4,
        day_of_month=None,
        run_hour=9,
        run_minute=30,
    )
    weekly_next = backup_service.calculate_next_backup_run(
        weekly_schedule,
        from_dt=datetime(2026, 3, 16, 8, 0),
    )
    assert weekly_next == datetime(2026, 3, 20, 9, 30)

    monthly_schedule = SimpleNamespace(
        enabled=True,
        frequency='Mensal',
        times_per_period=1,
        day_of_week=None,
        day_of_month=31,
        run_hour=10,
        run_minute=15,
    )
    monthly_next = backup_service.calculate_next_backup_run(
        monthly_schedule,
        from_dt=datetime(2026, 2, 20, 8, 0),
    )
    assert monthly_next == datetime(2026, 2, 28, 10, 15)


def test_backup_service_sqlite_path_checksum_and_cleanup(app, tmp_path, monkeypatch):
    valid_sqlite = tmp_path / 'valid.sqlite3'
    valid_sqlite.write_text('sqlite', encoding='utf-8')
    monkeypatch.setattr(
        backup_service,
        'db',
        SimpleNamespace(engine=SimpleNamespace(url=make_url(f"sqlite:///{valid_sqlite.as_posix()}"))),
    )
    valid_db_path, error_message = backup_service._resolve_sqlite_backup_database_path(app)
    assert error_message is None
    assert os.path.normpath(valid_db_path) == os.path.normpath(str(valid_sqlite))

    fake_db = SimpleNamespace(engine=SimpleNamespace(url=make_url('sqlite:///:memory:')))
    monkeypatch.setattr(backup_service, 'db', fake_db)
    db_path, error_message = backup_service._resolve_sqlite_backup_database_path(app)
    assert db_path is None
    assert 'inválido' in error_message

    missing_path = tmp_path / 'missing.sqlite3'
    monkeypatch.setattr(
        backup_service,
        'db',
        SimpleNamespace(engine=SimpleNamespace(url=make_url(f"sqlite:///{missing_path.as_posix()}"))),
    )
    db_path, error_message = backup_service._resolve_sqlite_backup_database_path(app)
    assert db_path is None
    assert 'não encontrado' in error_message

    checksum_path = tmp_path / 'checksum.txt'
    checksum_path.write_text('finora', encoding='utf-8')
    assert backup_service._calculate_file_checksum(str(checksum_path)) == hashlib.sha256(
        b'finora'
    ).hexdigest()
    backup_service._cleanup_storage_file(str(checksum_path))
    assert checksum_path.exists() is False


def test_backup_service_schedule_validation_paths(app, monkeypatch):
    monkeypatch.setattr(backup_service, 'record_activity', lambda *args, **kwargs: None)
    with app.app_context():
        user = User(username='scheduleuser', email='scheduleuser@example.com', name='Schedule User')
        user.set_password('Password123')
        db.session.add(user)
        db.session.commit()

        assert backup_service.apply_backup_schedule_update(
            user,
            {'enabled': '1', 'frequency': 'Nunca'},
            20,
        ) == 'invalid_frequency'
        assert backup_service.apply_backup_schedule_update(
            user,
            {'enabled': '1', 'frequency': 'Semanal', 'times_per_period': '99'},
            20,
        ) == 'invalid_times_per_period'
        assert backup_service.apply_backup_schedule_update(
            user,
            {'enabled': '1', 'frequency': 'Semanal', 'run_hour': '25'},
            20,
        ) == 'invalid_run_hour'
        assert backup_service.apply_backup_schedule_update(
            user,
            {'enabled': '1', 'frequency': 'Semanal', 'run_minute': '90'},
            20,
        ) == 'invalid_run_minute'
        assert backup_service.apply_backup_schedule_update(
            user,
            {'enabled': '1', 'frequency': 'Semanal', 'retention_count': '0'},
            20,
        ) == 'invalid_retention_count'
        assert backup_service.apply_backup_schedule_update(
            user,
            {'enabled': '1', 'frequency': 'Semanal', 'day_of_week': '9'},
            20,
        ) == 'invalid_day_of_week'
        assert backup_service.apply_backup_schedule_update(
            user,
            {'enabled': '1', 'frequency': 'Mensal', 'day_of_month': '42'},
            20,
        ) == 'invalid_day_of_month'
        assert backup_service.apply_backup_schedule_update(
            user,
            {
                'enabled': '1',
                'frequency': 'Mensal',
                'times_per_period': '2',
                'run_hour': '4',
                'run_minute': '15',
                'retention_count': '8',
                'day_of_month': '10',
            },
            20,
        ) is None

        db.session.refresh(user)
        assert user.backup_schedule.enabled is True
        assert user.backup_schedule.frequency == 'Mensal'
        assert user.backup_schedule.retention_count == 8
        assert user.backup_schedule.next_run_at is not None


def test_backup_service_maintenance_and_scheduler_short_circuit(app, monkeypatch):
    monkeypatch.setattr(backup_service, 'backup_schema_is_ready', lambda: False)
    assert backup_service.run_backup_maintenance(app) == {
        'processed_backups': 0,
        'affected_users': 0,
        'skipped': True,
    }

    monkeypatch.setattr(
        backup_service,
        'backup_schema_is_ready',
        lambda: (_ for _ in ()).throw(RuntimeError('boom')),
    )
    assert backup_service.run_backup_maintenance(app) == {
        'processed_backups': 0,
        'affected_users': 0,
        'skipped': True,
    }

    assert backup_service.start_backup_scheduler(app) is None

    app.config['TESTING'] = False
    app.config['ENABLE_BACKUP_SCHEDULER'] = False
    assert backup_service.start_backup_scheduler(app) is None


def test_backup_service_schedule_parse_and_persist_failures(app, monkeypatch):
    monkeypatch.setattr(backup_service, 'record_activity', lambda *args, **kwargs: None)
    with app.app_context():
        user = User(username='schedulefail', email='schedulefail@example.com', name='Schedule Fail')
        user.set_password('Password123')
        db.session.add(user)
        db.session.commit()
        backup_service.get_or_create_backup_schedule(user, 20)

        assert backup_service.apply_backup_schedule_update(
            user,
            {'enabled': '1', 'frequency': 'Semanal', 'run_hour': 'bad'},
            20,
        ) == 'invalid_schedule_value'

        def fail_commit():
            raise RuntimeError('commit failed')

        monkeypatch.setattr(db.session, 'commit', fail_commit)
        assert backup_service.apply_backup_schedule_update(
            user,
            {'enabled': '1', 'frequency': 'Semanal'},
            20,
        ) == 'backup_schedule_persist_failed'


def test_backup_service_start_scheduler_returns_stop_event(app, monkeypatch):
    monkeypatch.setattr(backup_service, 'run_backup_maintenance', lambda _app: None)
    app.config['TESTING'] = False
    app.config['ENABLE_BACKUP_SCHEDULER'] = True
    app.config['BACKUP_SCHEDULER_INTERVAL_SECONDS'] = 1

    stop_event = backup_service.start_backup_scheduler(app)

    assert stop_event is not None
    stop_event.set()


def test_update_service_manifest_error_paths_and_status_labels(app, tmp_path):
    app.config['UPDATE_MANIFEST_URL'] = ''
    with pytest.raises(ValueError, match='não configurado'):
        update_service.fetch_update_manifest(app)

    invalid_manifest = tmp_path / 'invalid-manifest.json'
    invalid_manifest.write_text(json.dumps({'channels': {'beta': {}}}), encoding='utf-8')
    app.config['UPDATE_MANIFEST_URL'] = str(invalid_manifest)
    with pytest.raises(ValueError, match='Canal de atualização'):
        update_service.fetch_update_manifest(app, channel='stable')

    assert update_service.get_update_status_label('unknown') == 'Desconhecido'
