import os
import sys
from threading import Thread

from config import DESKTOP_DATA_ROOT
from services.desktop_runtime import DesktopInstanceGuard
from services.desktop_shell import native_window_enabled, open_native_window


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
        if existing_url and native_window_enabled() and instance_guard.focus_existing_window():
            return 0
        if existing_url and _browser_auto_open_enabled():
            instance_guard.open_existing(existing_url)
        return 0

    server = None
    server_thread = None
    try:
        from waitress import create_server

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
        server = create_server(app, host='127.0.0.1', port=port)
        server_thread = Thread(target=server.run, name='finora-waitress', daemon=True)
        server_thread.start()
        runtime_state = instance_guard.publish(port)
        print(f'Starting FINORA in DESKTOP mode on port {port}...')
        print(f'Access at http://127.0.0.1:{port}')
        if native_window_enabled():
            try:
                open_native_window(runtime_state['url'], DESKTOP_DATA_ROOT)
            except Exception:
                app.logger.exception(
                    'A janela nativa não pôde ser iniciada; usando o navegador externo.'
                )
                if _browser_auto_open_enabled():
                    schedule_browser_open(port)
                server_thread.join()
        else:
            if _browser_auto_open_enabled():
                schedule_browser_open(port)
            server_thread.join()
        return 0
    finally:
        if server is not None:
            server.close()
        if server_thread is not None and server_thread.is_alive():
            server_thread.join(timeout=3)
        instance_guard.release()


if __name__ == '__main__':
    raise SystemExit(main())
