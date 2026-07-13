import json
import hashlib
import os
import time
import urllib.error
import urllib.request
import webbrowser
from datetime import datetime, timezone
from pathlib import Path


WINDOWS_ALREADY_EXISTS = 183


class DesktopInstanceGuard:
    """Owns the per-user desktop instance lock and its discoverable runtime state."""

    def __init__(self, data_root):
        self.data_root = Path(data_root).resolve()
        self.lock_path = self.data_root / 'finora.instance.lock'
        self.state_path = self.data_root / 'runtime.json'
        self._mutex_handle = None
        self._lock_file = None
        self._owns_lock = False

    def acquire(self):
        self.data_root.mkdir(parents=True, exist_ok=True)
        if os.name == 'nt':
            return self._acquire_windows_mutex()
        return self._acquire_file_lock()

    def _acquire_windows_mutex(self):
        import ctypes

        root_digest = hashlib.sha256(str(self.data_root).encode('utf-8')).hexdigest()[:24]
        mutex_name = f'Local\\FinoraDesktop-{root_digest}'
        kernel32 = ctypes.windll.kernel32
        kernel32.SetLastError(0)
        handle = kernel32.CreateMutexW(None, False, mutex_name)
        if not handle:
            raise OSError('Não foi possível criar a trava de instância do Finora.')
        if kernel32.GetLastError() == WINDOWS_ALREADY_EXISTS:
            kernel32.CloseHandle(handle)
            return False
        self._mutex_handle = handle
        self._owns_lock = True
        return True

    def _acquire_file_lock(self):
        import fcntl

        lock_file = open(self.lock_path, 'a+', encoding='utf-8')
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            lock_file.close()
            return False
        self._lock_file = lock_file
        self._owns_lock = True
        return True

    def publish(self, port):
        if not self._owns_lock:
            raise RuntimeError('A instância atual não possui a trava do Finora.')
        payload = {
            'pid': os.getpid(),
            'port': int(port),
            'url': f'http://127.0.0.1:{int(port)}/',
            'started_at': datetime.now(timezone.utc).isoformat(),
        }
        temporary_path = self.state_path.with_suffix('.tmp')
        temporary_path.write_text(json.dumps(payload, indent=2), encoding='utf-8')
        os.replace(temporary_path, self.state_path)
        return payload

    def wait_for_existing_url(self, timeout_seconds=6.0, poll_interval=0.2):
        deadline = time.monotonic() + max(float(timeout_seconds), 0.0)
        while time.monotonic() <= deadline:
            state = self.read_state()
            url = state.get('url') if state else None
            if url and self._is_healthy(url):
                return url
            time.sleep(max(float(poll_interval), 0.01))
        return None

    def read_state(self):
        try:
            payload = json.loads(self.state_path.read_text(encoding='utf-8'))
        except (OSError, ValueError, TypeError):
            return {}
        if not isinstance(payload, dict):
            return {}
        url = str(payload.get('url') or '')
        if not url.startswith('http://127.0.0.1:'):
            return {}
        return payload

    @staticmethod
    def _is_healthy(base_url):
        health_url = f"{base_url.rstrip('/')}/health"
        try:
            with urllib.request.urlopen(health_url, timeout=0.5) as response:  # nosec B310
                payload = json.load(response)
            return response.status == 200 and (
                payload.get('healthy') is True or payload.get('status') == 'ok'
            )
        except (OSError, ValueError, urllib.error.URLError):
            return False

    @staticmethod
    def open_existing(url):
        return webbrowser.open(url, new=0, autoraise=True)

    def focus_existing_window(self):
        if os.name != 'nt':
            return False
        state = self.read_state()
        target_pid = int(state.get('pid') or 0)
        if target_pid <= 0:
            return False

        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        matching_windows = []

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def enum_window(window_handle, _lparam):
            process_id = wintypes.DWORD()
            user32.GetWindowThreadProcessId(window_handle, ctypes.byref(process_id))
            if process_id.value == target_pid and user32.IsWindowVisible(window_handle):
                matching_windows.append(window_handle)
                return False
            return True

        user32.EnumWindows(enum_window, 0)
        if not matching_windows:
            return False
        window_handle = matching_windows[0]
        user32.ShowWindow(window_handle, 9)  # SW_RESTORE
        return bool(user32.SetForegroundWindow(window_handle))

    def release(self):
        if not self._owns_lock:
            return
        try:
            state = self.read_state()
            if state.get('pid') == os.getpid() and self.state_path.exists():
                self.state_path.unlink()
        except OSError:
            pass

        if self._mutex_handle is not None:
            import ctypes

            ctypes.windll.kernel32.CloseHandle(self._mutex_handle)
            self._mutex_handle = None
        if self._lock_file is not None:
            try:
                import fcntl

                fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_UN)
            finally:
                self._lock_file.close()
                self._lock_file = None
        self._owns_lock = False

    def __enter__(self):
        if not self.acquire():
            raise RuntimeError('Outra instância do Finora já está em execução.')
        return self

    def __exit__(self, _exc_type, _exc_value, _traceback):
        self.release()
