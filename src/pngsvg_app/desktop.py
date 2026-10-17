"""Desktop app: a native window (pywebview: WebView2 on Windows, WKWebView on macOS) around the local service.

The service runs in a background thread on 127.0.0.1 with a per-session token, exactly like `png2svg serve`.
Native open/save dialogs are offered to the page through `window.pywebview.api` (Bridge); file paths stay in
Python and never travel over HTTP.

    pngsvg-app              start the app
    pngsvg-app --smoke      start the service, vectorize one generated image, exit 0 (CI check, no window)
"""
from __future__ import annotations

import argparse
import io
import json
import multiprocessing
import os
import secrets
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

from . import free_port

TITLE = 'PNG to SVG Vectorize'
IMAGE_TYPES = ('Images (*.png;*.webp;*.jpg;*.jpeg)',)
PREFERRED_PORT = 47821   # a stable origin keeps the page's saved settings/language between runs


def data_dir() -> Path:
    """Per-user folder for the web view's storage (settings, language)."""
    import os
    if sys.platform == 'win32':
        base = Path(os.environ.get('LOCALAPPDATA') or Path.home() / 'AppData' / 'Local')
    elif sys.platform == 'darwin':
        base = Path.home() / 'Library' / 'Application Support'
    else:
        base = Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local' / 'share')
    path = base / TITLE
    path.mkdir(parents=True, exist_ok=True)
    return path


def pick_port() -> int:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(('127.0.0.1', PREFERRED_PORT))
            return PREFERRED_PORT
        except OSError:
            return free_port()


PREFS_FILE = 'settings.json'
_PREF_DEFAULTS = {'save_dir': None, 'ask_each_time': True, 'log': True}


def load_prefs(folder: Path | None = None) -> dict:
    """Desktop-only preferences (save folder, logging). A missing or broken file means defaults."""
    try:
        raw = json.loads(((folder or data_dir()) / PREFS_FILE).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        raw = {}
    prefs = dict(_PREF_DEFAULTS)
    if isinstance(raw, dict):
        if isinstance(raw.get('save_dir'), str) and Path(raw['save_dir']).is_dir():
            prefs['save_dir'] = raw['save_dir']
        for key in ('ask_each_time', 'log'):
            if isinstance(raw.get(key), bool):
                prefs[key] = raw[key]
    return prefs


def unique_path(folder: Path, filename: str) -> Path:
    """`folder/filename`, or name-2.svg, name-3.svg, ... so an existing file is never overwritten."""
    path, k = folder / filename, 1
    while path.exists():
        k += 1
        path = folder / f'{filename[:-4]}-{k}.svg'
    return path


class Bridge:
    """Methods callable from the page as window.pywebview.api.<name>(...). Underscored attributes are private.
    File paths stay here: the page only ever sees the chosen folder's path for display."""

    def __init__(self, jobs, server_module, prefs_dir: Path | None = None):
        self._jobs = jobs
        self._server = server_module
        self._window = None
        self._prefs_dir = prefs_dir
        self._prefs = load_prefs(prefs_dir)
        self._close_message = '{n} image(s) are still waiting or being processed. Close the app and stop them?'

    # -- preferences -------------------------------------------------------------------------------------------
    def _save_prefs(self) -> None:
        folder = self._prefs_dir or data_dir()
        (folder / PREFS_FILE).write_text(json.dumps(self._prefs, indent=2), encoding='utf-8')

    def get_prefs(self) -> dict:
        return dict(self._prefs, log_dir=str(self._prefs_dir or data_dir()))

    def set_pref(self, key: str, value) -> dict:
        """Only the boolean preferences can be set from the page; the folder comes from the native dialog."""
        if key in ('ask_each_time', 'log') and isinstance(value, bool):
            self._prefs[key] = value
            self._save_prefs()
        return self.get_prefs()

    def choose_save_dir(self) -> dict:
        folder = self._dialog('FOLDER', directory=self._prefs['save_dir'] or '')
        if folder:
            path = Path(folder if isinstance(folder, str) else folder[0])
            if path.is_dir():
                self._prefs['save_dir'] = str(path)
                self._save_prefs()
        return self.get_prefs()

    def clear_save_dir(self) -> dict:
        self._prefs['save_dir'] = None
        self._save_prefs()
        return self.get_prefs()

    def open_log_folder(self) -> bool:
        folder = self._prefs_dir or data_dir()
        try:
            if sys.platform == 'win32':
                os.startfile(folder)  # noqa: S606 - our own data folder
            else:
                subprocess.Popen(['open' if sys.platform == 'darwin' else 'xdg-open', str(folder)])  # noqa: S603
            return True
        except OSError:
            return False

    def open_url(self, url: str) -> bool:
        """Links in the About page open in the user's browser; only the project's own GitHub pages are allowed."""
        if not isinstance(url, str) or not url.startswith(f'https://github.com/{self._server.REPO}'):
            return False
        import webbrowser
        return webbrowser.open(url)

    # -- closing -----------------------------------------------------------------------------------------------
    def set_close_message(self, template: str) -> None:
        """The page sends the close confirmation in its own language ("{n}" = number of images)."""
        if isinstance(template, str) and '{n}' in template and len(template) < 400:
            self._close_message = template

    def _on_closing(self, window) -> None:
        """Ask before closing only while images are still waiting or being processed."""
        busy = self._jobs.busy()
        window.confirm_close = busy > 0
        if busy:
            window.localization['global.quitConfirmation'] = self._close_message.replace('{n}', str(busy))

    # -- files -------------------------------------------------------------------------------------------------
    def _dialog(self, kind: str, **kw):
        import webview
        kinds = getattr(webview, 'FileDialog', None)
        dialog = getattr(kinds, kind) if kinds else getattr(webview, f'{kind}_DIALOG')
        return self._window.create_file_dialog(dialog, **kw)

    def open_files(self) -> dict:
        """Native multi-select dialog; each readable image is put on the workbench (staged, not processed yet).
        Returns {'ids': [...], 'errors': [{'name': ..., 'code': ..., 'detail': ...}]}."""
        paths = self._dialog('OPEN', allow_multiple=True, file_types=IMAGE_TYPES) or []
        ids, errors = [], []
        for p in paths:
            path = Path(p)
            try:
                if path.stat().st_size > self._server.MAX_UPLOAD:
                    raise self._server.HTTPException(413, 'upload too large')
                data = path.read_bytes()
                w, h, _ = self._server.read_image(data, min(self._jobs.max_side, self._server.MAX_SIDE))
                ids.append(self._jobs.stage(self._server.clean_name(path.name), data, w, h).id)
            except Exception as e:  # noqa: BLE001 - reported to the page per file
                code = getattr(e, 'status_code', None) or (409 if type(e).__name__ == 'WorkbenchFull' else 400)
                errors.append({'name': self._server.clean_name(path.name), 'code': code,
                               'detail': str(getattr(e, 'detail', None) or e)[:200]})
        return {'ids': ids, 'errors': errors}

    def _output(self, job) -> tuple[str, str]:
        name = self._server.output_name(job.name, job.preset, self._jobs.name_pattern)
        return name, self._server.svg_output(job.svg, job.width, job.height, self._jobs.size_attrs)

    def _direct_dir(self) -> Path | None:
        """The save folder when the user chose one and does not want to be asked each time."""
        folder = self._prefs['save_dir']
        if folder and not self._prefs['ask_each_time'] and Path(folder).is_dir():
            return Path(folder)
        return None

    def save_svg(self, job_id: str) -> bool:
        job = self._jobs.get(str(job_id))
        if job is None or job.svg is None:
            return False
        name, text = self._output(job)
        folder = self._direct_dir()
        if folder:
            unique_path(folder, name).write_text(text, encoding='utf-8')
            return True
        target = self._dialog('SAVE', directory=self._prefs['save_dir'] or '', save_filename=name,
                              file_types=('SVG (*.svg)',))
        if not target:
            return False
        path = Path(target if isinstance(target, str) else target[0])
        if path.suffix.lower() != '.svg':
            path = path.with_suffix('.svg')
        path.write_text(text, encoding='utf-8')
        return True

    def save_all(self, job_ids: list) -> int:
        """Write every finished SVG into one folder; existing files are never overwritten (name-2.svg, ...)."""
        folder = self._direct_dir()
        if folder is None:
            chosen = self._dialog('FOLDER', directory=self._prefs['save_dir'] or '')
            if not chosen:
                return 0
            folder = Path(chosen if isinstance(chosen, str) else chosen[0])
        written = 0
        for jid in job_ids:
            job = self._jobs.get(str(jid))
            if job is None or job.svg is None:
                continue
            name, text = self._output(job)
            unique_path(folder, name).write_text(text, encoding='utf-8')
            written += 1
        return written


def _start_service(port: int, token: str):
    import uvicorn

    from . import server
    from .jobs import JobManager

    jobs = JobManager()
    jobs.start()
    app = server.create_app(jobs, token, {f'127.0.0.1:{port}', f'localhost:{port}'})
    srv = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=port, log_level='warning', access_log=False))
    thread = threading.Thread(target=srv.run, name='pngsvg-service', daemon=True)
    thread.start()
    deadline = time.time() + 30
    while not srv.started:
        if time.time() > deadline or not thread.is_alive():
            raise RuntimeError('local service did not start')
        time.sleep(0.05)
    return srv, jobs, server


def _request(port: int, token: str, path: str, data: bytes | None = None) -> dict:
    req = urllib.request.Request(f'http://127.0.0.1:{port}{path}', data=data, headers={'X-Token': token},
                                 method='POST' if data is not None else 'GET')
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def smoke(port: int, token: str) -> None:
    """Health check + one real vectorization through the worker pool (catches frozen-app packaging problems)."""
    from PIL import Image, ImageDraw
    health = _request(port, token, '/api/health')
    img = Image.new('RGB', (120, 90), (240, 244, 250))
    ImageDraw.Draw(img).ellipse((10, 10, 80, 80), fill=(37, 99, 235), outline=(15, 23, 42), width=3)
    buf = io.BytesIO()
    img.save(buf, 'PNG')
    job = _request(port, token, '/api/jobs?name=smoke.png', buf.getvalue())
    deadline = time.time() + 180
    while job['status'] not in ('done', 'error', 'cancelled'):
        if time.time() > deadline:
            raise RuntimeError('smoke job timed out')
        time.sleep(0.2)
        job = _request(port, token, f'/api/jobs/{job["id"]}')
    if job['status'] != 'done':
        raise RuntimeError(f'smoke job failed: {job.get("error")}')
    print(f'smoke ok: version {health["version"]}, {job["stats"]["regions"]} regions, {job["seconds"]} s', flush=True)


def main(argv=None) -> int:
    multiprocessing.freeze_support()
    ap = argparse.ArgumentParser(prog='pngsvg-app', description=f'{TITLE} desktop app')
    ap.add_argument('--smoke', action='store_true', help='start, vectorize one test image, exit (no window)')
    ap.add_argument('--debug', action='store_true', help='enable the web inspector')
    a = ap.parse_args(argv)
    if sys.stdout is None or sys.stderr is None:      # windowed build has no console: keep a log for support
        target = data_dir() / 'app.log' if load_prefs()['log'] else os.devnull     # Settings → Privacy
        log = open(target, 'a', encoding='utf-8', buffering=1)  # noqa: SIM115 - process lifetime
        sys.stdout = sys.stdout or log
        sys.stderr = sys.stderr or log

    port, token = (free_port() if a.smoke else pick_port()), secrets.token_urlsafe(32)
    srv, jobs, server = _start_service(port, token)
    try:
        if a.smoke:
            smoke(port, token)
            return 0
        import webview
        bridge = Bridge(jobs, server)
        bridge._window = webview.create_window(TITLE, f'http://127.0.0.1:{port}/#t={token}', js_api=bridge,
                                               width=1360, height=880, min_size=(900, 600),
                                               background_color='#F3EEE4')
        bridge._window.events.closing += bridge._on_closing
        webview.start(debug=a.debug, private_mode=False, storage_path=str(data_dir()))
        return 0
    except Exception as e:  # noqa: BLE001 - surfaced to the user; no image data in the message
        print(f'{TITLE}: {e}', file=sys.stderr)
        return 1
    finally:
        srv.should_exit = True
        jobs.shutdown()


if __name__ == '__main__':
    sys.exit(main())
