"""Job queue: images wait on a workbench until the user starts them, then run one (or a few) at a time in
low-priority worker processes. Progress and results are kept in memory only.

Statuses: staged (added, not started) → queued (waiting its turn) → running → done | error | cancelled.
"""
from __future__ import annotations

import io
import multiprocessing as mp
import os
import sys
import threading
import time
import uuid
from collections import OrderedDict, deque
from concurrent.futures import CancelledError, Future, ProcessPoolExecutor
from dataclasses import dataclass, field
from typing import Any

from PIL import Image

from pngsvg import options_for, vectorize
from pngsvg.presets import apply_overrides

MAX_JOBS = 200                       # oldest finished jobs are dropped beyond these limits
MAX_KEPT_BYTES = 512 * 1024 * 1024
MAX_STAGED = 100                     # default limit of photos waiting on the workbench at once

# Processing speed = how many images run at the same time. "auto" picks one from the machine at start-up.
SPEEDS = ('auto', 'saver', 'balanced', 'fast')


class WorkbenchFull(Exception):
    """Too many photos are waiting on the workbench."""


def cpu_count() -> int:
    return os.cpu_count() or 1


def total_ram_gb() -> float | None:
    """Physical memory in GB, or None when it cannot be read (no extra dependency)."""
    try:
        if sys.platform == 'win32':
            import ctypes

            class MemoryStatus(ctypes.Structure):
                _fields_ = [('dwLength', ctypes.c_ulong), ('dwMemoryLoad', ctypes.c_ulong),
                            ('ullTotalPhys', ctypes.c_ulonglong), ('ullAvailPhys', ctypes.c_ulonglong),
                            ('ullTotalPageFile', ctypes.c_ulonglong), ('ullAvailPageFile', ctypes.c_ulonglong),
                            ('ullTotalVirtual', ctypes.c_ulonglong), ('ullAvailVirtual', ctypes.c_ulonglong),
                            ('ullAvailExtendedVirtual', ctypes.c_ulonglong)]
            st = MemoryStatus()
            st.dwLength = ctypes.sizeof(MemoryStatus)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):
                return st.ullTotalPhys / 1024 ** 3
            return None
        return os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES') / 1024 ** 3
    except (AttributeError, OSError, ValueError):
        return None


def auto_speed(cpus: int, ram_gb: float | None) -> str:
    """Weak or unknown machines save resources; only clearly capable ones run two images at once."""
    if cpus >= 6 and ram_gb is not None and ram_gb >= 12:
        return 'balanced'
    return 'saver'


def concurrency_for(speed: str, cpus: int) -> int:
    if speed == 'fast':
        return max(1, min(4, cpus - 1))
    if speed == 'balanced':
        return 2 if cpus >= 4 else 1
    return 1


def _lower_priority() -> None:
    """Worker initializer: run below normal priority so the computer stays responsive."""
    try:
        if sys.platform == 'win32':
            import ctypes
            BELOW_NORMAL_PRIORITY_CLASS = 0x00004000
            ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(),
                                                    BELOW_NORMAL_PRIORITY_CLASS)
        else:
            os.nice(10)
    except (AttributeError, OSError):
        pass


@dataclass
class Job:
    id: str
    name: str
    preset: str
    options: dict[str, Any]
    source: bytes
    width: int
    height: int
    status: str = 'staged'           # staged | queued | running | done | error | cancelled
    stage: str = ''
    progress: float = 0.0
    position: int | None = None      # 1-based place in the queue while queued
    created: float = field(default_factory=time.time)
    started: float | None = None
    seconds: float | None = None
    svg: str | None = None
    stats: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    future: Future | None = None

    def public(self) -> dict[str, Any]:
        return {'id': self.id, 'name': self.name, 'preset': self.preset, 'options': self.options,
                'status': self.status, 'stage': self.stage, 'progress': round(self.progress, 3),
                'position': self.position, 'width': self.width, 'height': self.height, 'seconds': self.seconds,
                'source_bytes': len(self.source),
                'bytes': len(self.svg.encode()) if self.svg else None, 'stats': self.stats, 'error': self.error}


def build_options(preset: str, overrides: dict[str, Any], id_prefix: str):
    """Options for a preset plus validated overrides (see server.OptionsIn for the allowed fields/ranges)."""
    o = options_for(preset, id_prefix=id_prefix)
    # 'ai' / 'ai_auto' are handled before vectorizing (see _work)
    return apply_overrides(o, {k: v for k, v in overrides.items() if k not in ('ai', 'ai_auto')})


AI_TARGET = 2     # the AI result is traced at 2x the photo size (x4 model output, resized): see bench/ai_restore.py
AI_SMALL = 1000   # "automatic" AI: only photos smaller than this (longest side, px) or JPEGs, where it helps most


def wants_ai(options: dict[str, Any], source: bytes, width: int, height: int) -> bool:
    if not options.get('ai'):
        return False
    if not options.get('ai_auto'):
        return True
    return max(width, height) < AI_SMALL or source[:3] == b'\xff\xd8\xff'


def _work(job_id: str, source: bytes, preset: str, overrides: dict[str, Any], queue,
          ai: tuple[str, str] | None = None) -> dict[str, Any]:
    """Runs in a worker process. `ai` = (model file, accelerator) to clean/enlarge the photo first."""
    def stage(name: str, fraction: float) -> None:
        if queue is not None:
            queue.put((job_id, name, fraction))
    t = time.perf_counter()
    img = Image.open(io.BytesIO(source))
    opts = build_options(preset, overrides, 'v' + job_id[:8])
    if ai is not None:
        from pathlib import Path

        from pngsvg.ai import enhance
        stage('ai', 0.02)
        img = enhance(img, Path(ai[0]), ai[1], AI_TARGET)   # keeps transparency (remove background)
        if 'decimals' not in overrides:      # coordinates are AI_TARGET x larger: one decimal less, same precision
            opts.decimals = max(0, opts.decimals - 1)
        opts.regions.speckle *= AI_TARGET * AI_TARGET     # areas are in traced pixels
    res = vectorize(img, opts, on_stage=stage)
    return {'svg': res.svg, 'regions': res.regions, 'gradients': res.gradients, 'outline_paths': res.outline_paths,
            'palette': res.palette, 'seconds': time.perf_counter() - t, 'ai': bool(ai)}


class JobManager:
    def __init__(self, workers: int | None = None, speed: str = 'auto'):
        self._cpus = cpu_count()
        self._ram = total_ram_gb()
        self._fixed = workers                     # tests / CLI: a fixed number of simultaneous jobs
        self._speed = speed if speed in SPEEDS else 'auto'
        self.max_staged = MAX_STAGED
        self.max_side = 8000                  # longest side accepted (px); see server.MAX_SIDE
        self.name_pattern = '{name}'          # saved file names: {name} {style} {date} (or {nama} {gaya} {tanggal})
        self.size_attrs = False               # add width/height to saved SVGs (else viewBox only)
        self.models = None                    # pngsvg_app.models.ModelStore, for jobs with options['ai']
        self.ai_accel = 'auto'                # auto | gpu | cpu
        self._pool: ProcessPoolExecutor | None = None
        self._manager = None
        self._queue = None
        self._jobs: OrderedDict[str, Job] = OrderedDict()
        self._pending: deque[str] = deque()       # queued job ids, first in first out
        self._running: set[str] = set()           # ids holding a worker (a cancelled run still holds one)
        # Reentrant: a future that is already done runs its callback (_finish) inside _dispatch.
        self._lock = threading.RLock()
        self._listener: threading.Thread | None = None

    # -- settings --------------------------------------------------------------------------------------------
    def effective_speed(self) -> str:
        return auto_speed(self._cpus, self._ram) if self._speed == 'auto' else self._speed

    def concurrency(self) -> int:
        return self._fixed or concurrency_for(self.effective_speed(), self._cpus)

    def settings(self) -> dict[str, Any]:
        return {'speed': self._speed, 'effective': self.effective_speed(), 'concurrency': self.concurrency(),
                'auto': auto_speed(self._cpus, self._ram),
                'cpus': self._cpus, 'ram_gb': round(self._ram, 1) if self._ram else None,
                'speeds': {s: concurrency_for(s, self._cpus) for s in SPEEDS if s != 'auto'},
                'max_staged': self.max_staged, 'max_side': self.max_side, 'name_pattern': self.name_pattern,
                'size_attrs': self.size_attrs, 'ai_accel': self.ai_accel}

    def set_speed(self, speed: str) -> None:
        if speed not in SPEEDS:
            raise ValueError(f'speed must be one of {", ".join(SPEEDS)}')
        with self._lock:
            self._speed = speed
            self._dispatch()

    # -- lifecycle -------------------------------------------------------------------------------------------
    def start(self) -> None:
        if self._pool is not None:
            return
        most = self._fixed or concurrency_for('fast', self._cpus)
        self._pool = ProcessPoolExecutor(most, initializer=_lower_priority)
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

    def busy(self) -> int:
        """Images still waiting or running (the window asks before closing when this is not zero)."""
        with self._lock:
            return sum(1 for j in self._jobs.values() if j.status in ('queued', 'running'))

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
                if job and job.status == 'running':
                    job.stage, job.progress = name, fraction

    # -- jobs ------------------------------------------------------------------------------------------------
    def stage(self, name: str, source: bytes, width: int, height: int) -> Job:
        """Put a validated image on the workbench without processing it."""
        job = Job(uuid.uuid4().hex, name, 'cartoon', {}, source, width, height)
        with self._lock:
            if sum(1 for j in self._jobs.values() if j.status == 'staged') >= self.max_staged:
                raise WorkbenchFull(f'at most {self.max_staged} photos can wait on the workbench')
            self._jobs[job.id] = job
            self._trim()
        return job

    def start_jobs(self, ids: list[str], preset: str, overrides: dict[str, Any]) -> list[Job]:
        """Queue staged images with these settings, in the given order. Unknown or non-staged ids are skipped."""
        self.start()
        started = []
        with self._lock:
            for jid in ids:
                job = self._jobs.get(jid)
                if job is None or job.status != 'staged':
                    continue
                job.preset, job.options, job.status = preset, dict(overrides), 'queued'
                self._pending.append(job.id)
                started.append(job)
            self._dispatch()
        return started

    def submit(self, name: str, source: bytes, width: int, height: int, preset: str,
               overrides: dict[str, Any]) -> Job:
        """Stage and queue in one step (API clients, retry, smoke test)."""
        job = Job(uuid.uuid4().hex, name, preset, dict(overrides), source, width, height, status='queued')
        self.start()
        with self._lock:
            self._jobs[job.id] = job
            self._pending.append(job.id)
            self._trim()
            self._dispatch()
        return job

    def _dispatch(self) -> None:
        """Hand queued jobs to workers while fewer than `concurrency()` are running (caller holds the lock)."""
        while self._pending and len(self._running) < self.concurrency() and self._pool is not None:
            job = self._jobs.get(self._pending.popleft())
            if job is None or job.status != 'queued':
                continue
            ai = None
            if wants_ai(job.options, job.source, job.width, job.height):
                model = self.models.path(job.options['ai']) if self.models else None
                if model is None:                 # removed after the job was queued
                    job.status, job.error, job.position = 'error', 'AI model not installed', None
                    continue
                ai = (str(model), self.ai_accel)
            job.status, job.stage, job.progress, job.started = 'running', 'start', 0.0, time.time()
            self._running.add(job.id)
            job.future = self._pool.submit(_work, job.id, job.source, job.preset, job.options, self._queue, ai)
            job.future.add_done_callback(lambda f, j=job: self._finish(j, f))
        for i, jid in enumerate(self._pending):
            if (job := self._jobs.get(jid)) is not None:
                job.position = i + 1
        for jid in self._running:
            if (job := self._jobs.get(jid)) is not None:
                job.position = None

    def _finish(self, job: Job, fut: Future) -> None:
        with self._lock:
            self._running.discard(job.id)
            try:
                if job.status != 'cancelled':
                    try:
                        out = fut.result()
                    except CancelledError:
                        job.status = 'cancelled'
                    except Exception as e:  # noqa: BLE001 - reported to the UI, never the image content
                        job.status, job.error = 'error', f'{type(e).__name__}: {e}'[:300]
                    else:
                        job.svg = out.pop('svg')
                        job.seconds = round(out.pop('seconds'), 2)
                        job.stats = out
                        job.status, job.stage, job.progress = 'done', 'done', 1.0
            finally:
                self._dispatch()

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list(self) -> list[Job]:
        with self._lock:
            return list(self._jobs.values())

    def cancel(self, job_id: str) -> bool:
        """A waiting job leaves the queue at once; a running one is marked cancelled and its result discarded
        (the worker finishes the image in the background, then takes the next one)."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return False
            if job.status == 'queued':
                try:
                    self._pending.remove(job.id)
                except ValueError:
                    pass
                job.status, job.position = 'cancelled', None
                self._dispatch()
            elif job.status == 'running':
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
