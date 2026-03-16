import hashlib
import json
import os
import shutil
import subprocess  # nosec B404
import sys
import tempfile
import zipfile
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

from sqlalchemy import inspect

from database.db import db
from models.system import AppUpdateState
from models.time_utils import utcnow_naive
from services.profile_service import record_activity, record_system_event


UPDATE_REQUIRED_TABLES = frozenset({'app_update_state'})
UPDATE_STATUS_LABELS = {
    'idle': 'Pronto',
    'checking': 'Verificando',
    'available': 'Atualização disponível',
    'up_to_date': 'Atualizado',
    'not_configured': 'Não configurado',
    'applying': 'Aplicando atualização',
    'applied': 'Atualização aplicada',
    'error': 'Falha na atualização',
}
UPDATE_RUNTIME_EXCLUDES = frozenset({
    '.git',
    '.pytest_cache',
    '.ruff_cache',
    '.venv',
    '__pycache__',
    'backups',
    'logs',
    'updates',
})
UPDATE_SYNC_EXCLUDES = UPDATE_RUNTIME_EXCLUDES.union({'database'})
UPDATE_FILE_EXCLUDES = frozenset({
    '.env',
})
def update_schema_is_ready() -> bool:
    table_names = set(inspect(db.engine).get_table_names())
    return UPDATE_REQUIRED_TABLES.issubset(table_names)


def parse_version_tokens(version):
    normalized = (version or '').strip().lstrip('vV')
    if not normalized:
        return ((0, 0),)

    parts = []
    for raw_token in normalized.replace('-', '.').split('.'):
        token = raw_token.strip()
        if not token:
            continue
        if token.isdigit():
            parts.append((0, int(token)))
        else:
            parts.append((1, token.lower()))

    return tuple(parts or [(0, 0)])


def compare_versions(left_version, right_version):
    left_tokens = list(parse_version_tokens(left_version))
    right_tokens = list(parse_version_tokens(right_version))
    max_length = max(len(left_tokens), len(right_tokens))

    while len(left_tokens) < max_length:
        left_tokens.append((0, 0))
    while len(right_tokens) < max_length:
        right_tokens.append((0, 0))

    for left_token, right_token in zip(left_tokens, right_tokens, strict=False):
        if left_token < right_token:
            return -1
        if left_token > right_token:
            return 1
    return 0


def _get_update_target_root(app):
    return os.path.abspath(app.config.get('UPDATE_TARGET_ROOT') or app.root_path)


def _get_update_download_dir(app):
    update_dir = os.path.abspath(app.config.get('UPDATE_DOWNLOAD_DIR') or os.path.join(app.root_path, 'updates'))
    os.makedirs(update_dir, exist_ok=True)
    return update_dir


def get_or_create_update_state(app):
    state = AppUpdateState.query.order_by(AppUpdateState.id.asc()).first()
    installed_version = app.config.get('APP_VERSION', '1.3.0')
    update_channel = app.config.get('UPDATE_CHANNEL', 'stable')

    if state is None:
        state = AppUpdateState(
            installed_version=installed_version,
            latest_known_version=installed_version,
            update_channel=update_channel,
            status='idle',
        )
        db.session.add(state)
        db.session.commit()
        return state

    changed = False
    if state.installed_version != installed_version:
        state.installed_version = installed_version
        changed = True
    if state.update_channel != update_channel:
        state.update_channel = update_channel
        changed = True

    if changed:
        db.session.commit()

    return state


def get_update_status_label(status):
    return UPDATE_STATUS_LABELS.get(status or 'idle', 'Desconhecido')


def _open_source_stream(location, timeout_seconds):
    if os.path.exists(location):
        return open(location, 'rb')

    parsed = urlparse(location)
    if parsed.scheme == 'https':
        return urlopen(location, timeout=timeout_seconds)  # nosec B310
    if parsed.scheme:
        raise ValueError('Atualizacoes remotas aceitam apenas URLs HTTPS seguras.')
    raise ValueError('Origem de atualizacao invalida ou indisponivel.')


def _is_local_update_source(location):
    if not location:
        return False
    if os.path.exists(location):
        return True
    parsed = urlparse(location)
    return not parsed.scheme or parsed.scheme == 'file'


def _load_json_payload(location, timeout_seconds):
    with _open_source_stream(location, timeout_seconds) as payload_stream:
        return json.load(payload_stream)


def _extract_channel_payload(payload, channel):
    if not isinstance(payload, dict):
        raise ValueError('Manifesto de atualização inválido.')

    if 'channels' in payload and isinstance(payload['channels'], dict):
        payload = payload['channels']

    if channel in payload and isinstance(payload[channel], dict):
        return payload[channel]

    if 'version' in payload:
        return payload

    raise ValueError(f'Canal de atualização "{channel}" não encontrado no manifesto.')


def fetch_update_manifest(app, channel=None):
    manifest_location = (app.config.get('UPDATE_MANIFEST_URL') or '').strip()
    if not manifest_location:
        raise ValueError('Manifesto de atualização não configurado.')

    payload = _load_json_payload(
        manifest_location,
        int(app.config.get('UPDATE_CHECK_TIMEOUT_SECONDS', 10) or 10),
    )
    channel_name = (channel or app.config.get('UPDATE_CHANNEL', 'stable') or 'stable').strip()
    update_payload = _extract_channel_payload(payload, channel_name)
    manifest_is_local = _is_local_update_source(manifest_location)

    version = (update_payload.get('version') or '').strip()
    asset_url = (update_payload.get('asset_url') or update_payload.get('download_url') or '').strip()
    if not version:
        raise ValueError('Manifesto de atualização sem versão válida.')
    if (
        manifest_is_local
        and asset_url
        and _is_local_update_source(asset_url)
        and not bool(app.config.get('UPDATE_ALLOW_LOCAL_ASSETS', False))
    ):
        asset_url = ''

    return {
        'channel': channel_name,
        'version': version,
        'asset_url': asset_url,
        'sha256': (update_payload.get('sha256') or '').strip().lower() or None,
        'notes': update_payload.get('notes') or '',
        'requires_migration': bool(update_payload.get('requires_migration', True)),
        'manifest_is_local': manifest_is_local,
    }


def get_update_overview(app):
    state = get_or_create_update_state(app)
    manifest_location = (app.config.get('UPDATE_MANIFEST_URL') or '').strip()
    remote_manifest_configured = bool(manifest_location) and not _is_local_update_source(
        manifest_location
    )
    return {
        'update_state': state,
        'update_available': state.status == 'available',
        'update_status_label': get_update_status_label(state.status),
        'update_configured': bool(manifest_location),
        'update_remote_configured': remote_manifest_configured,
    }


def check_for_updates(app):
    state = get_or_create_update_state(app)
    state.status = 'checking'
    state.last_error = None
    db.session.commit()

    try:
        manifest = fetch_update_manifest(app, channel=state.update_channel)
        state.installed_version = app.config.get('APP_VERSION', state.installed_version)
        state.latest_known_version = manifest['version']
        state.last_checked_at = utcnow_naive()
        state.last_error = None
        has_update_package = bool((manifest.get('asset_url') or '').strip())
        state.status = (
            'available'
            if compare_versions(state.installed_version, manifest['version']) < 0 and has_update_package
            else 'up_to_date'
        )
        db.session.commit()
        return {
            'state': state,
            'manifest': manifest,
            'update_available': state.status == 'available',
        }
    except Exception as exc:
        db.session.rollback()
        state = get_or_create_update_state(app)
        state.last_checked_at = utcnow_naive()
        state.status = 'not_configured' if 'não configurado' in str(exc).lower() else 'error'
        state.last_error = str(exc)
        db.session.commit()
        return {
            'state': state,
            'manifest': None,
            'update_available': False,
            'error': str(exc),
        }


def _build_pre_update_backup(app, installed_version):
    target_root = _get_update_target_root(app)
    backup_dir = os.path.join(_get_update_download_dir(app), 'pre_update_backups')
    os.makedirs(backup_dir, exist_ok=True)

    timestamp = utcnow_naive().strftime('%Y%m%d_%H%M%S')
    backup_name = f'finora_pre_update_{installed_version}_{timestamp}.zip'
    backup_path = os.path.join(backup_dir, backup_name)

    with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as backup_zip:
        for root_dir, dir_names, file_names in os.walk(target_root):
            dir_names[:] = [name for name in dir_names if name not in UPDATE_RUNTIME_EXCLUDES]
            relative_root = os.path.relpath(root_dir, target_root)
            for file_name in file_names:
                if file_name in UPDATE_FILE_EXCLUDES:
                    continue
                source_path = os.path.join(root_dir, file_name)
                archive_name = file_name if relative_root == '.' else os.path.join(relative_root, file_name)
                backup_zip.write(source_path, archive_name)

    return backup_path


def _restore_pre_update_backup(target_root, backup_path):
    if not backup_path or not os.path.exists(backup_path):
        return

    with tempfile.TemporaryDirectory(prefix='finora-restore-') as restore_dir:
        _safe_extract_zip(backup_path, restore_dir)
        _sync_update_tree(restore_dir, target_root)


def _derive_asset_filename(asset_url, version):
    parsed = urlparse(asset_url)
    file_name = os.path.basename(parsed.path or '') or f'finora_update_{version}.zip'
    if not file_name.lower().endswith('.zip'):
        file_name = f'{file_name}.zip'
    return file_name


def _download_update_asset(app, manifest):
    asset_url = (manifest.get('asset_url') or '').strip()
    if not asset_url:
        raise ValueError('Manifesto sem pacote de atualização.')

    downloads_dir = os.path.join(_get_update_download_dir(app), 'downloads')
    os.makedirs(downloads_dir, exist_ok=True)
    package_path = os.path.join(downloads_dir, _derive_asset_filename(asset_url, manifest['version']))

    with _open_source_stream(asset_url, int(app.config.get('UPDATE_CHECK_TIMEOUT_SECONDS', 10) or 10)) as source_stream:
        with open(package_path, 'wb') as package_file:
            shutil.copyfileobj(source_stream, package_file)

    expected_sha = manifest.get('sha256')
    if expected_sha:
        actual_sha = _calculate_sha256(package_path)
        if actual_sha.lower() != expected_sha.lower():
            os.remove(package_path)
            raise ValueError('Checksum do pacote de atualização não confere.')

    return package_path


def _safe_extract_zip(zip_path, target_dir):
    target_path = Path(target_dir).resolve()
    with zipfile.ZipFile(zip_path, 'r') as archive:
        for member in archive.infolist():
            member_path = (target_path / member.filename).resolve()
            if not str(member_path).startswith(str(target_path)):
                raise ValueError('Pacote de atualização contém caminho inválido.')
        archive.extractall(target_dir)


def _looks_like_application_root(candidate_root):
    return (
        os.path.exists(os.path.join(candidate_root, 'app.py'))
        and os.path.isdir(os.path.join(candidate_root, 'routes'))
        and os.path.isdir(os.path.join(candidate_root, 'templates'))
    )


def _detect_package_root(extracted_dir):
    if _looks_like_application_root(extracted_dir):
        return extracted_dir

    child_directories = [
        os.path.join(extracted_dir, name)
        for name in os.listdir(extracted_dir)
        if os.path.isdir(os.path.join(extracted_dir, name))
    ]
    for child_dir in child_directories:
        if _looks_like_application_root(child_dir):
            return child_dir

    raise ValueError('Pacote de atualização não possui a estrutura esperada do Finora.')


def _sync_update_tree(source_root, target_root):
    for entry_name in os.listdir(source_root):
        if entry_name in UPDATE_SYNC_EXCLUDES or entry_name in UPDATE_FILE_EXCLUDES:
            continue

        source_path = os.path.join(source_root, entry_name)
        target_path = os.path.join(target_root, entry_name)

        if os.path.isdir(source_path):
            shutil.copytree(
                source_path,
                target_path,
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns(*UPDATE_SYNC_EXCLUDES, *UPDATE_FILE_EXCLUDES),
            )
        else:
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            shutil.copy2(source_path, target_path)


def _run_database_upgrade(app):
    target_root = _get_update_target_root(app)
    environment = _build_upgrade_environment(app)

    # Fixed interpreter command with sanitized cwd and environment.
    result = subprocess.run(  # nosec B603,B607
        [sys.executable, '-m', 'flask', 'db', 'upgrade'],
        cwd=target_root,
        env=environment,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    if result.returncode != 0:
        combined_output = (result.stderr or result.stdout or '').strip()
        raise RuntimeError(combined_output or 'Falha ao executar migrações após a atualização.')


def _calculate_sha256(file_path, chunk_size=1024 * 1024):
    digest = hashlib.sha256()
    with open(file_path, 'rb') as package_file:
        while True:
            chunk = package_file.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _build_upgrade_environment(app):
    safe_environment = {}
    passthrough_keys = (
        'PATH',
        'PATHEXT',
        'SYSTEMROOT',
        'WINDIR',
        'COMSPEC',
        'TEMP',
        'TMP',
        'HOME',
        'USERPROFILE',
        'APPDATA',
        'LOCALAPPDATA',
        'PROGRAMDATA',
        'VIRTUAL_ENV',
        'PYTHONPATH',
    )
    for env_key in passthrough_keys:
        env_value = os.environ.get(env_key)
        if env_value:
            safe_environment[env_key] = env_value

    safe_environment.update(
        {
            'FLASK_APP': 'app.py',
            'FLASK_ENV': 'production',
            'DATABASE_URL': app.config['SQLALCHEMY_DATABASE_URI'],
            'SECRET_KEY': app.config['SECRET_KEY'],
            'ENABLE_DEFAULT_USER_SEED': '0',
        }
    )

    app_base_url = (app.config.get('APP_BASE_URL') or '').strip()
    if app_base_url:
        safe_environment['APP_BASE_URL'] = app_base_url

    return safe_environment


def apply_update(app, user=None):
    state = get_or_create_update_state(app)
    state.status = 'applying'
    state.last_error = None
    db.session.commit()

    check_result = check_for_updates(app)
    manifest = check_result.get('manifest')
    if not manifest or not check_result.get('update_available'):
        state = get_or_create_update_state(app)
        return {
            'state': state,
            'applied': False,
            'manifest': manifest,
            'reason': check_result.get('error') or 'up_to_date',
        }

    target_root = _get_update_target_root(app)
    backup_path = None
    package_path = None

    try:
        backup_path = _build_pre_update_backup(app, state.installed_version)
        package_path = _download_update_asset(app, manifest)

        with tempfile.TemporaryDirectory(prefix='finora-update-') as extracted_dir:
            _safe_extract_zip(package_path, extracted_dir)
            package_root = _detect_package_root(extracted_dir)
            _sync_update_tree(package_root, target_root)

        if manifest.get('requires_migration', True):
            _run_database_upgrade(app)

        state = get_or_create_update_state(app)
        state.installed_version = manifest['version']
        state.latest_known_version = manifest['version']
        state.status = 'applied'
        state.last_downloaded_at = utcnow_naive()
        state.downloaded_asset_path = package_path
        state.last_error = None
        if user is not None:
            record_activity(
                user,
                'system',
                'update_applied',
                'Atualização do sistema aplicada com sucesso.',
                details={
                    'installed_version': manifest['version'],
                    'channel': manifest['channel'],
                    'backup_path': backup_path,
                },
                commit=False,
            )

        record_system_event(
            'info',
            'update',
            'Atualização do sistema aplicada com sucesso.',
            user=user,
            event_code='update_applied',
            details={
                'installed_version': manifest['version'],
                'channel': manifest['channel'],
                'backup_path': backup_path,
            },
            commit=False,
        )
        db.session.commit()
        return {
            'state': state,
            'applied': True,
            'manifest': manifest,
            'backup_path': backup_path,
            'package_path': package_path,
        }
    except Exception as exc:
        db.session.rollback()
        if backup_path:
            try:
                _restore_pre_update_backup(target_root, backup_path)
            except Exception:
                app.logger.exception('Falha ao restaurar snapshot pre-update apos erro de atualizacao.')

        state = get_or_create_update_state(app)
        state.status = 'error'
        state.last_error = str(exc)
        db.session.commit()

        record_system_event(
            'error',
            'update',
            'Falha ao aplicar atualização do sistema.',
            user=user,
            event_code='update_apply_failed',
            details={
                'error': str(exc),
                'backup_path': backup_path,
                'package_path': package_path,
            },
        )
        raise
