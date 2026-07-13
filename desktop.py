import os
import sys

from config import DESKTOP_DATA_ROOT
from services.desktop_runtime import DesktopInstanceGuard


def _browser_auto_open_enabled():
    return os.environ.get('FINORA_AUTO_OPEN_BROWSER', '1').strip().lower() in {
        '1',
        'true',
        'yes',
        'on',
    }


def main():
    instance_guard = DesktopInstanceGuard(DESKTOP_DATA_ROOT)
    if not instance_guard.acquire():
        existing_url = instance_guard.wait_for_existing_url()
        if existing_url and _browser_auto_open_enabled():
            instance_guard.open_existing(existing_url)
        return 0

    try:
        from waitress import serve

        from app import create_app, find_free_port, schedule_browser_open
        from services.backup_service import run_backup_maintenance, start_backup_scheduler
        from services.desktop_migration import migrate_legacy_desktop_data
        from services.maintenance_service import run_recurring_maintenance, start_recurring_scheduler

        migrate_legacy_desktop_data(DESKTOP_DATA_ROOT, sys.executable)
        app = create_app('desktop')
        port = find_free_port(5000)
        run_recurring_maintenance(app)
        start_recurring_scheduler(app)
        run_backup_maintenance(app)
        start_backup_scheduler(app)
        instance_guard.publish(port)
        print(f'Starting FINORA in DESKTOP mode on port {port}...')
        print(f'Access at http://127.0.0.1:{port}')
        schedule_browser_open(port)
        serve(app, host='127.0.0.1', port=port)
        return 0
    finally:
        instance_guard.release()


if __name__ == '__main__':
    raise SystemExit(main())
