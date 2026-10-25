"""Desktop watch folder: new pictures in a folder are queued like any other photo (they show up in the app) and each
finished result is written to the output folder in the chosen format."""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from pngsvg.watch import NewFiles, unique_path


class FolderWatch:
    def __init__(self, jobs, server_module, source: Path, target: Path, preset: str, overrides: dict[str, Any],
                 fmt: str, poll: float = 1.5):
        self._jobs = jobs
        self._server = server_module
        self.source, self.target = Path(source), Path(target)
        self.preset, self.overrides, self.fmt = preset, dict(overrides), fmt
        self._poll = poll
        self._stop = threading.Event()
        self._pending: dict[str, str] = {}          # job id -> picture name
        self.converted = self.failed = 0
        self.last_error: str | None = None
        self._new = NewFiles(self.source)
        self._thread = threading.Thread(target=self._run, name='pngsvg-watch', daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    @property
    def running(self) -> bool:
        return self._thread.is_alive() and not self._stop.is_set()

    def status(self) -> dict[str, Any]:
        return {'watching': self.running, 'source': str(self.source), 'target': str(self.target), 'format': self.fmt,
                'preset': self.preset, 'converted': self.converted, 'failed': self.failed,
                'waiting': len(self._pending), 'last_error': self.last_error}

    def _fail(self, name: str, why: str) -> None:
        self.failed += 1
        self.last_error = f'{name}: {why}'[:200]

    def _queue(self, path: Path) -> None:
        try:
            if path.stat().st_size > self._server.MAX_UPLOAD:
                return self._fail(path.name, 'file larger than 50 MB')
            data = path.read_bytes()
            w, h, _ = self._server.read_image(data, min(self._jobs.max_side, self._server.MAX_SIDE))
        except self._server.HTTPException as e:
            return self._fail(path.name, str(e.detail))
        except OSError as e:
            return self._fail(path.name, type(e).__name__)
        job = self._jobs.submit(self._server.clean_name(path.name), data, w, h, self.preset, self.overrides)
        self._pending[job.id] = path.name

    def _collect(self) -> None:
        for jid, name in list(self._pending.items()):
            job = self._jobs.get(jid)
            if job is None or job.status in ('error', 'cancelled'):
                self._fail(name, (job.error if job and job.error else 'stopped') if job else 'removed')
            elif job.status == 'done':
                try:
                    out, body = self._server.export_file(job, self.fmt, self._jobs)
                    self.target.mkdir(parents=True, exist_ok=True)
                    unique_path(self.target, out).write_bytes(body)
                    self.converted += 1
                except OSError as e:
                    self._fail(name, type(e).__name__)
            else:
                continue
            del self._pending[jid]

    def _run(self) -> None:
        while not self._stop.is_set():
            for path in self._new.poll():
                self._queue(path)
            self._collect()
            self._stop.wait(self._poll)
