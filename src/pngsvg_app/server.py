"""Local HTTP service for the UI: 127.0.0.1 only, a random per-session token on every /api request, Host check.

Nothing leaves the machine: images and results live in memory (jobs.JobManager) until the app exits.
"""
from __future__ import annotations

import hmac
import io
import json
import re
import unicodedata
import warnings
import zipfile
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field, ValidationError

import pngsvg
from pngsvg import PRESETS

from .jobs import JobManager

MAX_UPLOAD = 50 * 1024 * 1024          # bytes
MAX_SIDE = 8000                        # px, longest side
FORMATS = {'PNG': 'image/png', 'WEBP': 'image/webp', 'JPEG': 'image/jpeg'}
STATIC_DIR = Path(__file__).resolve().parent / 'static'
Image.MAX_IMAGE_PIXELS = MAX_SIDE * MAX_SIDE   # decompression-bomb guard (Pillow raises beyond 2x)

UI_CSP = ("default-src 'self'; img-src 'self' blob: data:; style-src 'self' 'unsafe-inline'; "
          "connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")


class OptionsIn(BaseModel):
    """Advanced settings the UI may override on top of a preset. Anything else is rejected."""
    model_config = ConfigDict(extra='forbid')
    outlines: bool | None = None
    gradients: bool | None = None
    radial: bool | None = None
    tolerance: float | None = Field(None, ge=0.1, le=3.0)
    smooth: float | None = Field(None, ge=0.0, le=5.0)
    merge_de: float | None = Field(None, ge=1.0, le=30.0)
    scale: int | None = Field(None, ge=1, le=4)


OPTION_SCHEMA = [
    {'name': 'outlines', 'type': 'bool'},
    {'name': 'gradients', 'type': 'bool'},
    {'name': 'radial', 'type': 'bool'},
    {'name': 'tolerance', 'type': 'float', 'min': 0.1, 'max': 3.0, 'step': 0.05},
    {'name': 'smooth', 'type': 'float', 'min': 0.0, 'max': 5.0, 'step': 0.1},
    {'name': 'merge_de', 'type': 'float', 'min': 1.0, 'max': 30.0, 'step': 0.5},
    {'name': 'scale', 'type': 'int', 'min': 1, 'max': 4, 'step': 1},
]


def _preset_defaults(name: str) -> dict[str, Any]:
    o = pngsvg.options_for(name)
    return {'outlines': o.outlines, 'gradients': o.gradients, 'radial': o.radial, 'tolerance': o.tolerance,
            'smooth': o.smooth, 'merge_de': o.regions.merge_de, 'scale': o.scale}


def clean_name(name: str | None) -> str:
    """Display name only (never used as a path): last path component, printable, at most 120 chars."""
    base = re.split(r'[\\/]', name or '')[-1]
    base = ''.join(ch for ch in unicodedata.normalize('NFC', base) if unicodedata.category(ch)[0] != 'C')
    return base.strip()[:120] or 'image'


def svg_filename(name: str) -> str:
    stem = name.rsplit('.', 1)[0] if '.' in name else name
    return (stem or 'image') + '.svg'


def _disposition(filename: str, attachment: bool) -> str:
    ascii_name = re.sub(r'[^A-Za-z0-9._ -]', '_', filename) or 'image.svg'
    from urllib.parse import quote
    kind = 'attachment' if attachment else 'inline'
    return f"{kind}; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"


def read_image(data: bytes) -> tuple[int, int, str]:
    """Validate by content (not extension): PNG/WebP/JPEG, bounded dimensions. Returns (w, h, format)."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as im:
                fmt = im.format
                w, h = im.size
                im.verify()
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise HTTPException(413, 'image dimensions too large')
    except Exception:
        raise HTTPException(415, 'not a readable PNG, WebP or JPEG image')
    if fmt not in FORMATS:
        raise HTTPException(415, 'only PNG, WebP and JPEG images are supported')
    if max(w, h) > MAX_SIDE:
        raise HTTPException(413, f'image too large: longest side must be <= {MAX_SIDE} px')
    if min(w, h) < 2:
        raise HTTPException(415, 'image too small')
    return w, h, fmt


def parse_options(preset: str, options: str | None) -> dict[str, Any]:
    if preset not in PRESETS:
        raise HTTPException(422, f'unknown preset; choose one of: {", ".join(PRESETS)}')
    if not options:
        return {}
    try:
        raw = json.loads(options)
        return OptionsIn.model_validate(raw).model_dump(exclude_none=True)
    except (json.JSONDecodeError, ValidationError) as e:
        raise HTTPException(422, f'invalid options: {str(e)[:300]}')


async def read_body(request: Request) -> bytes:
    length = request.headers.get('content-length')
    if length and length.isdigit() and int(length) > MAX_UPLOAD:
        raise HTTPException(413, f'upload too large (max {MAX_UPLOAD // (1024 * 1024)} MB)')
    chunks, size = [], 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > MAX_UPLOAD:
            raise HTTPException(413, f'upload too large (max {MAX_UPLOAD // (1024 * 1024)} MB)')
        chunks.append(chunk)
    return b''.join(chunks)


def create_app(jobs: JobManager, token: str, allowed_hosts: set[str], static_dir: Path = STATIC_DIR) -> FastAPI:
    app = FastAPI(title='PNG to SVG Vectorize', version=pngsvg.__version__, docs_url=None, redoc_url=None,
                  openapi_url=None)

    @app.middleware('http')
    async def guard(request: Request, call_next):
        host = request.headers.get('host', '')
        if host not in allowed_hosts:                       # DNS rebinding: only our own origin
            return JSONResponse({'detail': 'host not allowed'}, status_code=400)
        if request.url.path.startswith('/api'):
            given = request.headers.get('x-token', '')
            if not hmac.compare_digest(given.encode(), token.encode()):
                return JSONResponse({'detail': 'missing or invalid token'}, status_code=401)
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        if request.url.path.startswith('/api'):
            response.headers.setdefault('Cache-Control', 'no-store')
        elif response.headers.get('content-type', '').startswith('text/html'):
            response.headers['Content-Security-Policy'] = UI_CSP
        return response

    @app.get('/api/health')
    def health():
        return {'status': 'ok', 'version': pngsvg.__version__}

    @app.get('/api/presets')
    def presets():
        return {'presets': [{'name': k, 'description': v, 'defaults': _preset_defaults(k)} for k, v in PRESETS.items()],
                'options': OPTION_SCHEMA, 'limits': {'max_upload': MAX_UPLOAD, 'max_side': MAX_SIDE,
                                                     'formats': sorted(FORMATS)}}

    @app.post('/api/jobs', status_code=201)
    async def create_job(request: Request, name: str = Query(''), preset: str = Query('cartoon'),
                         options: str | None = Query(None)):
        overrides = parse_options(preset, options)
        data = await read_body(request)
        w, h, _ = read_image(data)
        return jobs.submit(clean_name(name), data, w, h, preset, overrides).public()

    @app.get('/api/jobs')
    def list_jobs():
        return {'jobs': [j.public() for j in jobs.list()]}

    def _job(job_id: str):
        job = jobs.get(job_id)
        if job is None:
            raise HTTPException(404, 'job not found')
        return job

    @app.get('/api/jobs/{job_id}')
    def get_job(job_id: str):
        return _job(job_id).public()

    @app.get('/api/jobs/{job_id}/svg')
    def get_svg(job_id: str, download: bool = False):
        job = _job(job_id)
        if job.status != 'done' or job.svg is None:
            raise HTTPException(409, 'result not ready')
        return Response(job.svg, media_type='image/svg+xml',
                        headers={'Content-Disposition': _disposition(svg_filename(job.name), download),
                                 'Content-Security-Policy': "default-src 'none'; style-src 'unsafe-inline'"})

    @app.get('/api/jobs/{job_id}/source')
    def get_source(job_id: str):
        job = _job(job_id)
        fmt = Image.open(io.BytesIO(job.source)).format
        return Response(job.source, media_type=FORMATS.get(fmt, 'application/octet-stream'))

    @app.post('/api/jobs/{job_id}/retry', status_code=201)
    def retry(job_id: str, preset: str | None = Query(None), options: str | None = Query(None)):
        job = _job(job_id)
        p = preset or job.preset
        overrides = parse_options(p, options) if (options is not None or preset is not None) else job.options
        return jobs.submit(job.name, job.source, job.width, job.height, p, overrides).public()

    @app.post('/api/jobs/{job_id}/cancel')
    def cancel(job_id: str):
        if not jobs.cancel(job_id):
            raise HTTPException(404, 'job not found')
        return _job(job_id).public()

    @app.delete('/api/jobs/{job_id}')
    def delete(job_id: str):
        if not jobs.remove(job_id):
            raise HTTPException(404, 'job not found')
        return {'deleted': job_id}

    @app.get('/api/export.zip')
    def export_zip(ids: str = Query(..., max_length=20000)):
        buf, used = io.BytesIO(), set()
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
            for jid in ids.split(','):
                job = jobs.get(jid.strip())
                if job is None or job.status != 'done' or job.svg is None:
                    continue
                fname, k = svg_filename(job.name), 1
                while fname.lower() in used:
                    k += 1
                    fname = svg_filename(job.name)[:-4] + f'-{k}.svg'
                used.add(fname.lower())
                z.writestr(fname, job.svg)
        if not used:
            raise HTTPException(409, 'no finished results to export')
        return Response(buf.getvalue(), media_type='application/zip',
                        headers={'Content-Disposition': _disposition('png2svg-results.zip', True)})

    if (static_dir / 'index.html').exists():
        app.mount('/', StaticFiles(directory=static_dir, html=True), name='ui')
    else:
        @app.get('/', response_class=HTMLResponse)
        def missing_ui():
            return ('<!doctype html><meta charset="utf-8"><title>PNG to SVG Vectorize</title>'
                    '<p>The user interface has not been built. Run <code>npm ci &amp;&amp; npm run build</code> in '
                    '<code>app/ui</code>, then restart. The API is available under <code>/api</code>.</p>')

    return app
