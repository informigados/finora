import sys
from types import SimpleNamespace

from services.desktop_shell import native_window_enabled, open_native_window


def test_native_window_is_default_and_can_be_disabled(monkeypatch):
    monkeypatch.delenv('FINORA_DESKTOP_SHELL', raising=False)
    assert native_window_enabled() is True
    monkeypatch.setenv('FINORA_DESKTOP_SHELL', 'browser')
    assert native_window_enabled() is False


def test_native_window_uses_persistent_edge_webview_storage(tmp_path, monkeypatch):
    calls = {}

    def create_window(*args, **kwargs):
        calls['create_window'] = (args, kwargs)

    def start(**kwargs):
        calls['start'] = kwargs

    fake_webview = SimpleNamespace(
        settings={},
        create_window=create_window,
        start=start,
    )
    monkeypatch.setitem(sys.modules, 'webview', fake_webview)

    open_native_window('http://127.0.0.1:5000', tmp_path)

    args, kwargs = calls['create_window']
    assert args == ('Finora', 'http://127.0.0.1:5000')
    assert kwargs['resizable'] is True
    assert kwargs['min_size'] == (960, 640)
    assert calls['start']['gui'] == 'edgechromium'
    assert calls['start']['private_mode'] is False
    assert calls['start']['storage_path'] == str(tmp_path / 'webview')
    assert fake_webview.settings['OPEN_EXTERNAL_LINKS_IN_BROWSER'] is True
