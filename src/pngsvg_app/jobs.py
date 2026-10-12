"""Job queue: each image is vectorized in a worker process; progress and results are kept in memory only."""
from __future__ import annotations

import io
import multiprocessing as mp
import os
import threading
import time
import uuid
from collections import OrderedDict
from concurrent.futures import CancelledError, Future, ProcessPoolExecutor
from dataclasses import dataclass, field
from typing import Any

from PIL import Image

from pngsvg import options_for, vectorize

MAX_JOBS = 200                       # oldest finished jobs are dropped beyond these limits
MAX_KEPT_BYTES = 512 * 1024 * 1024


@dataclass
class Job:
    id: str
    name: str
    preset: str
    options: dict[str, Any]
    source: bytes
    width: int
    height: int
    status: str = 'queued'           # queued | running | done | error | cancelled
    stage: str = ''
    progress: float = 0.0
    created: float = field(default_factory=time.time)
    started: float | None = None
    seconds: float | None = None
    svg: str | None = None
    stats: dict[str, int] = field(default_factory=dict)
    error: str | None = None
    future: Future | None = None

    def public(self) -> dict[str, Any]:
        return {'id': self.id, 'name': self.name, 'preset': self.preset, 'options': self.options,
                'status': self.status, 'stage': self.stage, 'progress': round(self.progress, 3),
                'width': self.width, 'height': self.height, 'seconds': self.seconds,
                'bytes': len(self.svg.encode()) if self.svg else None, 'stats': self.stats, 'error': self.error}


def build_options(preset: str, overrides: dict[str, Any], id_prefix: str):
    """Options for a preset plus validated overrides (see server.OptionsIn for the allowed fields/ranges)."""
    o = options_for(preset, id_prefix=id_prefix)
    for key, value in overrides.items():
        if value is None:
            continue
        if key == 'merge_de':
            o.regions.merge_de = float(value)
        else:
            setattr(o, key, value)
    return o


def _work(job_id: str, source: bytes, preset: str, overrides: dict[str, Any], queue) -> dict[str, Any]:
    """Runs in a worker process."""
    def stage(name: str, fraction: float) -> None:
        if queue is not None:
            queue.put((job_id, name, fraction))
    t = time.perf_counter()
    img = Image.open(io.BytesIO(source))
    res = vectorize(img, build_options(preset, overrides, 'v' + job_id[:8]), on_stage=stage)
    return {'svg': res.svg, 'regions': res.regions, 'gradients': res.gradients, 'outline_paths': res.outline_paths,
            'seconds': time.perf_counter() - t}


class JobManager:
    def __init__(self, workers: int | None = None):
        self._workers = workers or min(4, os.cpu_count() or 1)
        self._pool: ProcessPoolExecutor | None = None
        self._manager = None
        self._queue = None
        self._jobs: OrderedDict[str, Job] = OrderedDict()
        self._lock = threading.Lock()
        self._listener: threading.Thread | None = None

    # -- lifecycle -------------------------------------------------------------------------------------------
    def start(self) -> None:
        if self._pool is not None:
            return
        self._pool = ProcessPoolExecutor(self._workers)
        self._manager = mp.Manager()
        self._queue = self._manager.Queue()
        self._listener = threading.Thread(target=self._listen, name='pngsvg-progress', daemon=True)
        self._listener.start()

    def shutdown(self) -> None:
        if self._pool is None:
            return
        self._pool.shutdown(wait=False, cancel_futures=True)
        self._queue.put(None)
        self._manager.shutdown()
        self._pool = self._manager = self._queue = None

    def _listen(self) -> None:
        q = self._queue
        while True:
            try:
                item = q.get()
            except (EOFError, OSError):
                return
            if item is None:
                return
            job_id, name, fraction = item
            with self._lock:
                job = self._jobs.get(job_id)
                if job and job.status in ('queued', 'running'):
                    job.status, job.stage, job.progress = 'running', name, fraction
                    job.started = job.started or time.time()

    # -- jobs ------------------------------------------------------------------------------------------------
    def submit(self, name: str, source: bytes, width: int, height: int, preset: str,
               overrides: dict[str, Any]) -> Job:
        self.start()
        job = Job(uuid.uuid4().hex, name, preset, overrides, source, width, height)
        with self._lock:
            self._jobs[job.id] = job
            self._trim()
        job.future = self._pool.submit(_work, job.id, source, preset, overrides, self._queue)
        job.future.add_done_callback(lambda f, j=job: self._finish(j, f))
        return job

    def _finish(self, job: Job, fut: Future) -> None:
        with self._lock:
            if job.status == 'cancelled':
                return
            try:
                out = fut.result()
            except CancelledError:
                job.status = 'cancelled'
                return
            except Exception as e:  # noqa: BLE001 - reported to the UI, never the image content
                job.status, job.error = 'error', f'{type(e).__name__}: {e}'[:300]
                return
            job.svg = out.pop('svg')
            job.seconds = round(out.pop('seconds'), 2)
            job.stats = out
            job.status, job.stage, job.progress = 'done', 'done', 1.0

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list(self) -> list[Job]:
        with self._lock:
            return list(self._jobs.values())

    def cancel(self, job_id: str) -> bool:
        """Queued jobs are cancelled; a running job is marked cancelled and its result discarded."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return False
            if job.status in ('queued', 'running'):
                if job.future is not None:
                    job.future.cancel()
                job.status = 'cancelled'
            return True

    def remove(self, job_id: str) -> bool:
        self.cancel(job_id)
        with self._lock:
            return self._jobs.pop(job_id, None) is not None

    def _trim(self) -> None:
        """Drop the oldest finished jobs beyond MAX_JOBS / MAX_KEPT_BYTES (caller holds the lock)."""
        def size() -> int:
            return sum(len(j.source) + (len(j.svg) if j.svg else 0) for j in self._jobs.values())
        for jid in list(self._jobs):
            if len(self._jobs) <= MAX_JOBS and size() <= MAX_KEPT_BYTES:
                break
            if self._jobs[jid].status in ('done', 'error', 'cancelled'):
                del self._jobs[jid]
