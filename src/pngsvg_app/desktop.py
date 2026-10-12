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
import secrets
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


class Bridge:
    """Methods callable from the page as window.pywebview.api.<name>(...). Underscored attributes are private."""

    def __init__(self, jobs, server_module):
        self._jobs = jobs
        self._server = server_module
        self._window = None

    def _dialog(self, kind: str, **kw):
        import webview
        kinds = getattr(webview, 'FileDialog', None)
        dialog = getattr(kinds, kind) if kinds else getattr(webview, f'{kind}_DIALOG')
        return self._window.create_file_dialog(dialog, **kw)

    def open_files(self, preset: str = 'cartoon', overrides: dict | None = None) -> dict:
        """Native multi-select dialog; each readable image becomes a job with the page's current settings.
        Returns {'ids': [...], 'errors': [...]}."""
        paths = self._dialog('OPEN', allow_multiple=True, file_types=IMAGE_TYPES) or []
        ids, errors = [], []
        settings = {'preset': preset if isinstance(preset, str) else 'cartoon',
                    'overrides': overrides if isinstance(overrides, dict) else {}}
        for p in paths:
            path = Path(p)
            try:
                if path.stat().st_size > self._server.MAX_UPLOAD:
                    raise ValueError('file too large')
                data = path.read_bytes()
                w, h, _ = self._server.read_image(data)
                overrides = self._server.parse_options(settings['preset'], json.dumps(settings['overrides']))
                ids.append(self._jobs.submit(self._server.clean_name(path.name), data, w, h, settings['preset'],
                                             overrides).id)
            except Exception as e:  # noqa: BLE001 - reported to the page per file
                errors.append(f'{path.name}: {getattr(e, "detail", None) or e}')
        return {'ids': ids, 'errors': errors}

    def save_svg(self, job_id: str) -> bool:
        job = self._jobs.get(str(job_id))
        if job is None or job.svg is None:
            return False
        target = self._dialog('SAVE', save_filename=self._server.svg_filename(job.name),
                              file_types=('SVG (*.svg)',))
        if not target:
            return False
        path = Path(target if isinstance(target, str) else target[0])
        if path.suffix.lower() != '.svg':
            path = path.with_suffix('.svg')
        path.write_text(job.svg, encoding='utf-8')
        return True

    def save_all(self, job_ids: list) -> int:
        """Pick a folder and write every finished SVG; existing files are never overwritten (name-2.svg, ...)."""
        folder = self._dialog('FOLDER')
        if not folder:
            return 0
        folder = Path(folder if isinstance(folder, str) else folder[0])
        written = 0
        for jid in job_ids:
            job = self._jobs.get(str(jid))
            if job is None or job.svg is None:
                continue
            base = self._server.svg_filename(job.name)
            path, k = folder / base, 1
            while path.exists():
                k += 1
                path = folder / f'{base[:-4]}-{k}.svg'
            path.write_text(job.svg, encoding='utf-8')
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
        log = open(data_dir() / 'app.log', 'a', encoding='utf-8', buffering=1)  # noqa: SIM115 - process lifetime
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
                                               width=1360, height=880, min_size=(900, 600))
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
