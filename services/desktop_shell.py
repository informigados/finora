import os
from pathlib import Path


def native_window_enabled():
    value = os.environ.get('FINORA_DESKTOP_SHELL', 'native').strip().lower()
    return value not in {'browser', 'external', '0', 'false', 'off'}


def open_native_window(url, data_root):
    import webview

    storage_path = Path(data_root) / 'webview'
    storage_path.mkdir(parents=True, exist_ok=True)
    webview.settings['ALLOW_DOWNLOADS'] = True
    webview.settings['OPEN_EXTERNAL_LINKS_IN_BROWSER'] = True
    webview.settings['OPEN_DEVTOOLS_IN_DEBUG'] = False
    webview.create_window(
        'Finora',
        url,
        width=1280,
        height=820,
        min_size=(960, 640),
        resizable=True,
        background_color='#f4f7fb',
    )
    webview.start(
        gui='edgechromium',
        debug=False,
        private_mode=False,
        storage_path=str(storage_path),
    )
