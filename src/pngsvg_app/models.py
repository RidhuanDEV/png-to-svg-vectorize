"""AI model files for the optional "Enhance with AI" step: downloaded once, on request, from this project's own GitHub
release, verified by SHA-256, stored in the user's data folder. Nothing is downloaded unless the user asks.
"""
from __future__ import annotations

import hashlib
import os
import sys
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

RELEASE = 'https://github.com/RidhuanDEV/png-to-svg-vectorize/releases/download/models-v1'


@dataclass(frozen=True)
class ModelInfo:
    name: str          # id used by the API and the UI
    file: str
    bytes: int
    sha256: str
    source: str        # where the weights come from (shown in About / licenses)


# Converted with tools/models/convert.py from the official Real-ESRGAN weights (BSD-3-Clause).
CATALOG: dict[str, ModelInfo] = {
    'illustration': ModelInfo('illustration', 'illustration-x4.onnx', 17939943,
                              'e2236af4709b1c599ca80b4a8c86fe50c392564db35d33646dfa513f82638a68',
                              'Real-ESRGAN RealESRGAN_x4plus_anime_6B (BSD-3-Clause)'),
    'general': ModelInfo('general', 'general-x4.onnx', 4866396,
                         '924ebad6532777303582d4ce7811849b88869231a3ae7093e0f21200249df8d5',
                         'Real-ESRGAN realesr-general-x4v3 (BSD-3-Clause)'),
}


def data_dir(app: str = 'PNG to SVG Vectorize') -> Path:
    """Per-user data folder (same as the desktop app's)."""
    if sys.platform == 'win32':
        base = Path(os.environ.get('LOCALAPPDATA') or Path.home() / 'AppData' / 'Local')
    elif sys.platform == 'darwin':
        base = Path.home() / 'Library' / 'Application Support'
    else:
        base = Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local' / 'share')
    return base / app


class ModelStore:
    def __init__(self, folder: Path | None = None, release: str = RELEASE, catalog: dict[str, ModelInfo] = CATALOG):
        self.folder = folder or data_dir() / 'models'
        self.release = release
        self.catalog = catalog
        self._state: dict[str, dict] = {}
        self._cancel: dict[str, threading.Event] = {}
        self._lock = threading.Lock()

    def path(self, name: str) -> Path | None:
        """The verified model file, or None when it is not installed."""
        info = self.catalog.get(name)
        if info is None:
            return None
        p = self.folder / info.file
        return p if p.is_file() and p.stat().st_size == info.bytes else None

    def status(self) -> list[dict]:
        out = []
        with self._lock:
            for name, info in self.catalog.items():
                st = dict(self._state.get(name, {}))
                installed = self.path(name) is not None
                state = st.get('state') or ('installed' if installed else 'missing')
                if state == 'installed' and not installed:
                    state = 'missing'
                out.append({'name': name, 'bytes': info.bytes, 'source': info.source, 'state': state,
                            'progress': st.get('progress', 1.0 if installed else 0.0), 'error': st.get('error')})
        return out

    def download(self, name: str) -> None:
        """Start a background download (no-op if installed or already downloading)."""
        info = self.catalog[name]
        with self._lock:
            if self._state.get(name, {}).get('state') == 'downloading' or self.path(name):
                return
            self._state[name] = {'state': 'downloading', 'progress': 0.0}
            self._cancel[name] = threading.Event()
        threading.Thread(target=self._fetch, args=(info,), name=f'model-{name}', daemon=True).start()

    def cancel(self, name: str) -> None:
        ev = self._cancel.get(name)
        if ev:
            ev.set()

    def remove(self, name: str) -> None:
        info = self.catalog[name]
        self.cancel(name)
        for p in (self.folder / info.file, self.folder / (info.file + '.part')):
            try:
                p.unlink()
            except FileNotFoundError:
                pass
        with self._lock:
            self._state.pop(name, None)

    def _set(self, name: str, **kw) -> None:
        with self._lock:
            self._state[name] = {**self._state.get(name, {}), **kw}

    def _fetch(self, info: ModelInfo) -> None:
        self.folder.mkdir(parents=True, exist_ok=True)
        part = self.folder / (info.file + '.part')
        url = f'{self.release}/{info.file}'
        digest, got = hashlib.sha256(), 0
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'pngsvg-model-download'})
            with urllib.request.urlopen(req, timeout=30) as r, part.open('wb') as f:  # noqa: S310 - fixed https URL
                while True:
                    if self._cancel[info.name].is_set():
                        raise InterruptedError('cancelled')
                    chunk = r.read(1 << 16)
                    if not chunk:
                        break
                    got += len(chunk)
                    if got > info.bytes:
                        raise ValueError('file is larger than expected')
                    digest.update(chunk)
                    f.write(chunk)
                    self._set(info.name, progress=got / info.bytes)
            if got != info.bytes or digest.hexdigest() != info.sha256:
                raise ValueError('the downloaded file is not the expected one')
            os.replace(part, self.folder / info.file)
            self._set(info.name, state='installed', progress=1.0, error=None)
        except InterruptedError:
            part.unlink(missing_ok=True)
            self._set(info.name, state='missing', progress=0.0, error=None)
        except (urllib.error.URLError, OSError, ValueError, TimeoutError) as e:
            part.unlink(missing_ok=True)
            reason = 'checksum' if isinstance(e, ValueError) else 'network'
            self._set(info.name, state='error', progress=0.0, error=reason)
