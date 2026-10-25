"""Local service + UI for pngsvg (web mode: `png2svg serve`; desktop app: pywebview shell)."""
from __future__ import annotations

import multiprocessing
import secrets
import socket
import webbrowser

__all__ = ['serve', 'free_port']


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def serve(port: int = 0, token: str | None = None, open_browser: bool = True, workers: int | None = None) -> None:
    """Run the local service on 127.0.0.1 (blocking) and optionally open the UI in the default browser."""
    import uvicorn

    from .jobs import JobManager
    from .server import create_app

    multiprocessing.freeze_support()
    port = port or free_port()
    token = token or secrets.token_urlsafe(32)
    jobs = JobManager(workers)
    from .models import ModelStore
    jobs.models = ModelStore()
    app = create_app(jobs, token, {f'127.0.0.1:{port}', f'localhost:{port}'})
    url = f'http://127.0.0.1:{port}/#t={token}'
    print(f'PNG to SVG Vectorize is running at {url}\n(the link contains this session\'s access token; '
          f'press Ctrl+C to stop)', flush=True)
    if open_browser:
        webbrowser.open(url)
    jobs.start()
    try:
        uvicorn.run(app, host='127.0.0.1', port=port, log_level='warning', access_log=False)
    finally:
        jobs.shutdown()
