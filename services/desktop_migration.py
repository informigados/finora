import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from config import migrate_local_secret_key


LEGACY_DATABASE_RELATIVE_PATHS = (
    Path('_internal/database/finora.db'),
    Path('database/finora.db'),
)


def _find_legacy_database(executable_path):
    executable_root = Path(executable_path).resolve().parent
    for relative_path in LEGACY_DATABASE_RELATIVE_PATHS:
        candidate = executable_root / relative_path
        if candidate.is_file():
            return candidate
    return None


def migrate_legacy_desktop_data(data_root, executable_path):
    """Moves a pre-1.4 packaged profile into the per-user desktop data root once."""
    data_root = Path(data_root).resolve()
    target_database = data_root / 'database' / 'finora.db'
    if target_database.exists():
        return {'migrated': False, 'reason': 'target_exists'}

    legacy_database = _find_legacy_database(executable_path)
    if legacy_database is None:
        return {'migrated': False, 'reason': 'legacy_not_found'}

    legacy_root = legacy_database.parent.parent
    target_database.parent.mkdir(parents=True, exist_ok=True)
    temporary_database = target_database.with_suffix('.migrating')
    try:
        shutil.copy2(legacy_database, temporary_database)
        if temporary_database.stat().st_size == 0:
            raise ValueError('O banco de dados legado está vazio.')
        os.replace(temporary_database, target_database)

        for suffix in ('-wal', '-shm'):
            legacy_sidecar = Path(f'{legacy_database}{suffix}')
            if legacy_sidecar.is_file():
                shutil.copy2(legacy_sidecar, Path(f'{target_database}{suffix}'))

        legacy_secret = legacy_database.parent / '.finora_secret_key'
        target_secret = target_database.parent / '.finora_secret_key'
        if legacy_secret.is_file():
            migrate_local_secret_key(str(legacy_secret), str(target_secret))

        _copy_directory_contents(
            legacy_root / 'static' / 'profile_pics',
            data_root / 'static' / 'profile_pics',
            excluded_names={'default_profile.svg', 'default_profile.png'},
        )
        _copy_directory_contents(legacy_root / 'backups', data_root / 'backups')

        migration_record = {
            'migrated': True,
            'source': str(legacy_root),
            'database': str(target_database),
            'migrated_at': datetime.now(timezone.utc).isoformat(),
        }
        marker_path = data_root / 'migration-from-pre-1.4.json'
        marker_path.write_text(json.dumps(migration_record, indent=2), encoding='utf-8')
        return migration_record
    except Exception:
        if temporary_database.exists():
            temporary_database.unlink()
        if target_database.exists():
            target_database.unlink()
        raise


def _copy_directory_contents(source_dir, target_dir, excluded_names=None):
    if not source_dir.is_dir():
        return
    excluded_names = set(excluded_names or ())
    target_dir.mkdir(parents=True, exist_ok=True)
    for source_path in source_dir.iterdir():
        if source_path.name in excluded_names:
            continue
        target_path = target_dir / source_path.name
        if source_path.is_dir():
            shutil.copytree(source_path, target_path, dirs_exist_ok=True)
        elif source_path.is_file():
            shutil.copy2(source_path, target_path)
