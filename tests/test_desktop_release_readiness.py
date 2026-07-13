import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from config import get_or_create_local_secret_key
from services import update_service
from services import desktop_runtime
from services.desktop_migration import migrate_legacy_desktop_data
from services.desktop_runtime import DesktopInstanceGuard


def test_desktop_instance_guard_allows_only_one_owner(tmp_path, monkeypatch):
    first_guard = DesktopInstanceGuard(tmp_path)
    second_guard = DesktopInstanceGuard(tmp_path)

    assert first_guard.acquire() is True
    state = first_guard.publish(5123)
    assert state['url'] == 'http://127.0.0.1:5123/'
    assert second_guard.acquire() is False

    monkeypatch.setattr(second_guard, '_is_healthy', lambda _url: True)
    assert second_guard.wait_for_existing_url(timeout_seconds=0.1) == state['url']

    first_guard.release()
    assert not (tmp_path / 'runtime.json').exists()
    assert second_guard.acquire() is True
    second_guard.release()


def test_desktop_instance_guard_rejects_untrusted_runtime_url(tmp_path):
    guard = DesktopInstanceGuard(tmp_path)
    guard.data_root.mkdir(parents=True, exist_ok=True)
    guard.state_path.write_text(
        json.dumps({'pid': 10, 'url': 'https://example.com/'}),
        encoding='utf-8',
    )
    assert guard.read_state() == {}


def test_base_template_uses_only_bundled_frontend_dependencies():
    template = Path('templates/base.html').read_text(encoding='utf-8')
    assert 'cdn.jsdelivr.net' not in template
    assert 'unpkg.com' not in template
    assert 'fonts.googleapis.com' not in template
    assert "vendor/bootstrap/bootstrap.min.css" in template
    assert "vendor/chartjs/chart.umd.min.js" in template
    assert "vendor/lucide/lucide.min.js" in template


def test_desktop_asset_filename_requires_executable():
    assert update_service._derive_asset_filename(
        'https://example.com/Finora_Setup_v1.5.0.exe',
        '1.5.0',
        desktop_mode=True,
    ) == 'Finora_Setup_v1.5.0.exe'
    with pytest.raises(ValueError, match='instalador EXE'):
        update_service._derive_asset_filename(
            'https://example.com/finora-update.zip',
            '1.5.0',
            desktop_mode=True,
        )


def test_authenticode_validation_requires_valid_expected_publisher(monkeypatch):
    monkeypatch.setattr(update_service.os, 'name', 'nt')
    monkeypatch.setattr(
        update_service,
        '_get_powershell_executable',
        lambda: 'powershell.exe',
    )
    monkeypatch.setattr(
        update_service.subprocess,
        'run',
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0,
            stdout=json.dumps({'Status': 'Valid', 'Subject': 'CN=INformigados'}),
        ),
    )
    signature = update_service._verify_desktop_installer_signature(
        'Finora_Setup.exe',
        expected_publisher='INformigados',
    )
    assert signature['Status'] == 'Valid'

    with pytest.raises(ValueError, match='publicador'):
        update_service._verify_desktop_installer_signature(
            'Finora_Setup.exe',
            expected_publisher='Outro Publicador',
        )


def test_desktop_update_stages_verified_installer_without_source_sync(app, tmp_path, monkeypatch):
    installer_path = tmp_path / 'Finora_Setup_v1.5.0.exe'
    installer_path.write_bytes(b'signed-installer')
    staged = []

    manifest = {
        'channel': 'stable',
        'version': '1.5.0',
        'asset_url': 'https://example.com/Finora_Setup_v1.5.0.exe',
        'sha256': 'a' * 64,
        'publisher': 'INformigados',
        'requires_migration': True,
    }
    app.config.update(
        DESKTOP_MODE=True,
        DESKTOP_DATA_ROOT=str(tmp_path / 'data'),
        TESTING=True,
    )
    monkeypatch.setattr(
        update_service,
        'check_for_updates',
        lambda _app: {'manifest': manifest, 'update_available': True},
    )
    monkeypatch.setattr(
        update_service,
        '_build_pre_update_backup',
        lambda *_args: str(tmp_path / 'pre-update.zip'),
    )
    monkeypatch.setattr(
        update_service,
        '_download_update_asset',
        lambda *_args: str(installer_path),
    )
    monkeypatch.setattr(
        update_service,
        '_verify_desktop_installer_signature',
        lambda *_args, **_kwargs: {'Status': 'Valid', 'Subject': 'CN=INformigados'},
    )
    monkeypatch.setattr(update_service, '_stage_desktop_installer', staged.append)
    monkeypatch.setattr(update_service, 'record_system_event', lambda *_args, **_kwargs: None)

    with app.app_context():
        result = update_service.apply_update(app)

    assert result['applied'] is True
    assert result['desktop_staged'] is True
    assert staged == [str(installer_path)]


def test_legacy_packaged_profile_migrates_once_without_losing_secret(tmp_path, monkeypatch):
    monkeypatch.delenv('SECRET_KEY', raising=False)
    install_root = tmp_path / 'Program Files' / 'Finora'
    legacy_root = install_root / '_internal'
    legacy_database_dir = legacy_root / 'database'
    legacy_database_dir.mkdir(parents=True)
    legacy_database = legacy_database_dir / 'finora.db'
    legacy_database.write_bytes(b'SQLite format 3\x00legacy-data')
    legacy_secret_path = legacy_database_dir / '.finora_secret_key'
    original_secret = get_or_create_local_secret_key(str(legacy_secret_path))

    profile_dir = legacy_root / 'static' / 'profile_pics'
    profile_dir.mkdir(parents=True)
    (profile_dir / 'avatar.png').write_bytes(b'avatar')
    (profile_dir / 'default_profile.svg').write_text('default', encoding='utf-8')
    backup_dir = legacy_root / 'backups'
    backup_dir.mkdir()
    (backup_dir / 'legacy.zip').write_bytes(b'backup')

    data_root = tmp_path / 'LocalAppData' / 'Finora'
    result = migrate_legacy_desktop_data(data_root, install_root / 'Finora.exe')

    target_database = data_root / 'database' / 'finora.db'
    target_secret = data_root / 'database' / '.finora_secret_key'
    assert result['migrated'] is True
    assert target_database.read_bytes() == legacy_database.read_bytes()
    assert get_or_create_local_secret_key(str(target_secret)) == original_secret
    assert (data_root / 'static' / 'profile_pics' / 'avatar.png').exists()
    assert not (data_root / 'static' / 'profile_pics' / 'default_profile.svg').exists()
    assert (data_root / 'backups' / 'legacy.zip').exists()
    assert (data_root / 'migration-from-pre-1.4.json').exists()

    second_result = migrate_legacy_desktop_data(data_root, install_root / 'Finora.exe')
    assert second_result == {'migrated': False, 'reason': 'target_exists'}


def test_desktop_runtime_state_health_and_context_edges(tmp_path, monkeypatch):
    guard = DesktopInstanceGuard(tmp_path)
    with pytest.raises(RuntimeError, match='não possui'):
        guard.publish(5000)
    assert guard.read_state() == {}
    guard.state_path.write_text('[]', encoding='utf-8')
    assert guard.read_state() == {}
    guard.state_path.write_text('{invalid', encoding='utf-8')
    assert guard.read_state() == {}
    assert guard.wait_for_existing_url(timeout_seconds=0, poll_interval=0.01) is None
    assert guard.release() is None

    class HealthyResponse(io.BytesIO):
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.close()

    monkeypatch.setattr(
        'services.desktop_runtime.urllib.request.urlopen',
        lambda *_args, **_kwargs: HealthyResponse(b'{"status":"ok"}'),
    )
    assert guard._is_healthy('http://127.0.0.1:5000/') is True
    monkeypatch.setattr(
        'services.desktop_runtime.urllib.request.urlopen',
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError('offline')),
    )
    assert guard._is_healthy('http://127.0.0.1:5000/') is False
    monkeypatch.setattr('services.desktop_runtime.webbrowser.open', lambda *args, **kwargs: (args, kwargs))
    opened = guard.open_existing('http://127.0.0.1:5000/')
    assert opened[0][0] == 'http://127.0.0.1:5000/'

    with DesktopInstanceGuard(tmp_path / 'context') as owned_guard:
        assert owned_guard._owns_lock is True
    assert owned_guard._owns_lock is False

    blocked_guard = DesktopInstanceGuard(tmp_path / 'blocked')
    monkeypatch.setattr(blocked_guard, 'acquire', lambda: False)
    with pytest.raises(RuntimeError, match='já está'):
        blocked_guard.__enter__()


def test_desktop_runtime_portable_file_lock_path(tmp_path, monkeypatch):
    guard = DesktopInstanceGuard(tmp_path)
    lock_operations = []
    fake_fcntl = SimpleNamespace(
        LOCK_EX=1,
        LOCK_NB=2,
        LOCK_UN=4,
        flock=lambda descriptor, operation: lock_operations.append((descriptor, operation)),
    )
    monkeypatch.setitem(sys.modules, 'fcntl', fake_fcntl)
    monkeypatch.setattr(desktop_runtime.os, 'name', 'posix')
    assert guard.acquire() is True
    assert guard._lock_file is not None
    guard.release()
    assert guard._lock_file is None
    assert [operation for _descriptor, operation in lock_operations] == [3, 4]


def test_desktop_runtime_windows_mutex_paths(tmp_path, monkeypatch):
    handles = iter((101, 202, 0))
    last_errors = iter((0, desktop_runtime.WINDOWS_ALREADY_EXISTS))
    closed_handles = []
    kernel32 = SimpleNamespace(
        SetLastError=lambda _value: None,
        CreateMutexW=lambda *_args: next(handles),
        GetLastError=lambda: next(last_errors),
        CloseHandle=closed_handles.append,
    )
    monkeypatch.setitem(
        sys.modules,
        'ctypes',
        SimpleNamespace(windll=SimpleNamespace(kernel32=kernel32)),
    )

    owner = DesktopInstanceGuard(tmp_path / 'owner')
    assert owner._acquire_windows_mutex() is True
    assert owner._mutex_handle == 101
    owner.release()
    assert owner._mutex_handle is None

    duplicate = DesktopInstanceGuard(tmp_path / 'duplicate')
    assert duplicate._acquire_windows_mutex() is False

    unavailable = DesktopInstanceGuard(tmp_path / 'unavailable')
    with pytest.raises(OSError, match='criar a trava'):
        unavailable._acquire_windows_mutex()

    assert closed_handles == [101, 202]


def test_legacy_migration_fresh_and_failure_paths(tmp_path):
    data_root = tmp_path / 'data'
    executable = tmp_path / 'Finora' / 'Finora.exe'
    assert migrate_legacy_desktop_data(data_root, executable) == {
        'migrated': False,
        'reason': 'legacy_not_found',
    }

    empty_database = executable.parent / 'database' / 'finora.db'
    empty_database.parent.mkdir(parents=True)
    empty_database.write_bytes(b'')
    with pytest.raises(ValueError, match='vazio'):
        migrate_legacy_desktop_data(data_root, executable)
    assert not (data_root / 'database' / 'finora.db').exists()


def test_desktop_download_requires_hash_and_valid_checksum(app, tmp_path):
    source = tmp_path / 'Finora_Setup_v1.5.0.exe'
    source.write_bytes(b'installer')
    app.config.update(
        DESKTOP_MODE=True,
        UPDATE_DOWNLOAD_DIR=str(tmp_path / 'downloads'),
    )
    manifest = {
        'version': '1.5.0',
        'asset_url': str(source),
        'sha256': None,
    }
    with pytest.raises(ValueError, match='exigem checksum'):
        update_service._download_update_asset(app, manifest)

    manifest['sha256'] = '0' * 64
    with pytest.raises(ValueError, match='não confere'):
        update_service._download_update_asset(app, manifest)

    manifest['asset_url'] = ''
    with pytest.raises(ValueError, match='sem pacote'):
        update_service._download_update_asset(app, manifest)


def test_authenticode_validation_failure_paths(monkeypatch):
    monkeypatch.setattr(update_service.os, 'name', 'posix')
    with pytest.raises(RuntimeError, match='só pode'):
        update_service._verify_desktop_installer_signature('installer.exe')

    monkeypatch.setattr(update_service.os, 'name', 'nt')
    monkeypatch.setattr(
        update_service,
        '_get_powershell_executable',
        lambda: 'powershell.exe',
    )
    responses = iter(
        (
            SimpleNamespace(returncode=1, stdout=''),
            SimpleNamespace(returncode=0, stdout='not-json'),
            SimpleNamespace(returncode=0, stdout=json.dumps({'Status': 'NotSigned'})),
        )
    )
    monkeypatch.setattr(update_service.subprocess, 'run', lambda *_args, **_kwargs: next(responses))
    with pytest.raises(RuntimeError, match='Não foi possível'):
        update_service._verify_desktop_installer_signature('installer.exe')
    with pytest.raises(RuntimeError, match='Resposta inválida'):
        update_service._verify_desktop_installer_signature('installer.exe')
    with pytest.raises(ValueError, match='não possui'):
        update_service._verify_desktop_installer_signature('installer.exe')


def test_powershell_resolution_prefers_system_binary(tmp_path, monkeypatch):
    system_root = tmp_path / 'Windows'
    system_powershell = (
        system_root / 'System32' / 'WindowsPowerShell' / 'v1.0' / 'powershell.exe'
    )
    system_powershell.parent.mkdir(parents=True)
    system_powershell.touch()
    monkeypatch.setenv('SYSTEMROOT', str(system_root))
    assert update_service._get_powershell_executable() == str(system_powershell)

    system_powershell.unlink()
    monkeypatch.setattr(update_service.shutil, 'which', lambda _name: 'C:\\PowerShell.exe')
    assert update_service._get_powershell_executable() == 'C:\\PowerShell.exe'

    monkeypatch.setattr(update_service.shutil, 'which', lambda _name: None)
    with pytest.raises(RuntimeError, match='não está disponível'):
        update_service._get_powershell_executable()


def test_desktop_installer_staging_and_shutdown_helpers(monkeypatch):
    popen_calls = []
    monkeypatch.setattr(
        update_service,
        '_get_powershell_executable',
        lambda: 'powershell.exe',
    )
    monkeypatch.setattr(update_service.subprocess, 'Popen', lambda *args, **kwargs: popen_calls.append((args, kwargs)))
    monkeypatch.setattr(update_service.subprocess, 'CREATE_NO_WINDOW', 8, raising=False)
    update_service._stage_desktop_installer('C:\\Updates\\Finora_Setup.exe')
    assert popen_calls[0][1]['creationflags'] == 8

    timer = SimpleNamespace(daemon=False, started=False)
    monkeypatch.setattr(
        update_service.threading,
        'Timer',
        lambda *_args, **_kwargs: timer,
    )
    timer.start = lambda: setattr(timer, 'started', True)
    update_service._schedule_desktop_shutdown(0.1)
    assert timer.daemon is True
    assert timer.started is True
