import io
import json
import time
import xml.etree.ElementTree as ET
import zipfile

import pytest
from PIL import Image, ImageDraw

pytest.importorskip('fastapi')
pytest.importorskip('httpx')
from fastapi.testclient import TestClient  # noqa: E402

from pngsvg_app import server  # noqa: E402
from pngsvg_app.jobs import JobManager  # noqa: E402

TOKEN = 'test-token'
H = {'X-Token': TOKEN}


def png(size=(160, 120), fmt='PNG') -> bytes:
    img = Image.new('RGB', size, (240, 244, 250))
    d = ImageDraw.Draw(img)
    d.ellipse((20, 15, 90, 85), fill=(37, 99, 235), outline=(15, 23, 42), width=3)
    d.rectangle((80, 50, 140, 105), fill=(245, 158, 11))
    buf = io.BytesIO()
    img.save(buf, fmt)
    return buf.getvalue()


@pytest.fixture(scope='module')
def jobs():
    m = JobManager(workers=1)
    m.start()
    yield m
    m.shutdown()


@pytest.fixture()
def client(jobs, tmp_path):
    app = server.create_app(jobs, TOKEN, {'testserver'}, static_dir=tmp_path)
    with TestClient(app) as c:
        yield c


def wait(client, job_id, timeout=180):
    end = time.time() + timeout
    while time.time() < end:
        j = client.get(f'/api/jobs/{job_id}', headers=H).json()
        if j['status'] in ('done', 'error', 'cancelled'):
            return j
        time.sleep(0.2)
    raise AssertionError('job did not finish')


def test_token_is_required(client):
    assert client.get('/api/health').status_code == 401
    assert client.get('/api/health', headers={'X-Token': 'wrong'}).status_code == 401
    r = client.get('/api/health', headers=H)
    assert r.status_code == 200 and r.json()['status'] == 'ok'
    assert r.headers['cache-control'] == 'no-store'


def test_foreign_host_is_rejected(client):
    r = client.get('/api/health', headers={**H, 'Host': 'evil.example:8080'})
    assert r.status_code == 400


def test_ui_page_needs_no_token_and_has_csp(client):
    r = client.get('/')
    assert r.status_code == 200
    assert "default-src 'self'" in r.headers['content-security-policy']


def test_presets_endpoint(client):
    body = client.get('/api/presets', headers=H).json()
    assert {p['name'] for p in body['presets']} == {'cartoon', 'flat', 'logo', 'poster'}
    assert {o['name'] for o in body['options']} >= {'tolerance', 'outlines', 'scale'}


def test_upload_size_limit(client, monkeypatch):
    monkeypatch.setattr(server, 'MAX_UPLOAD', 200)
    r = client.post('/api/jobs?name=a.png', content=png(), headers=H)
    assert r.status_code == 413


def test_non_image_and_unsupported_format(client):
    assert client.post('/api/jobs', content=b'hello world', headers=H).status_code == 415
    gif = io.BytesIO()
    Image.new('RGB', (20, 20)).save(gif, 'GIF')
    assert client.post('/api/jobs', content=gif.getvalue(), headers=H).status_code == 415


def test_dimension_limit(client, monkeypatch):
    monkeypatch.setattr(server, 'MAX_SIDE', 100)
    assert client.post('/api/jobs', content=png((200, 50)), headers=H).status_code == 413


@pytest.mark.parametrize('query', ['options={"tolerance": 99}', 'options={"evil": 1}', 'options=notjson',
                                   'preset=nope'])
def test_invalid_options_are_rejected(client, query):
    assert client.post(f'/api/jobs?{query}', content=png(), headers=H).status_code == 422


def test_full_job_flow(client):
    opts = json.dumps({'tolerance': 0.6})
    r = client.post(f'/api/jobs?name=../../secret/scene%00.png&preset=cartoon&options={opts}', content=png(),
                    headers=H)
    assert r.status_code == 201
    job = r.json()
    assert job['name'] == 'scene.png' and job['options'] == {'tolerance': 0.6}
    done = wait(client, job['id'])
    assert done['status'] == 'done', done
    assert done['stats']['regions'] > 0 and done['bytes'] > 0 and done['seconds'] is not None

    svg = client.get(f'/api/jobs/{job["id"]}/svg', headers=H)
    assert svg.headers['content-type'].startswith('image/svg+xml')
    assert svg.headers['content-disposition'].startswith('inline')
    tags = {el.tag.split('}')[-1] for el in ET.fromstring(svg.text).iter()}
    assert tags <= {'svg', 'defs', 'linearGradient', 'radialGradient', 'stop', 'g', 'rect', 'path'}
    dl = client.get(f'/api/jobs/{job["id"]}/svg?download=true', headers=H)
    assert dl.headers['content-disposition'].startswith('attachment') and 'scene.svg' in dl.headers['content-disposition']

    src = client.get(f'/api/jobs/{job["id"]}/source', headers=H)
    assert src.headers['content-type'] == 'image/png' and src.content[:4] == b'\x89PNG'

    z = client.get(f'/api/export.zip?ids={job["id"]},missing', headers=H)
    assert z.status_code == 200
    assert zipfile.ZipFile(io.BytesIO(z.content)).namelist() == ['scene.svg']

    assert any(j['id'] == job['id'] for j in client.get('/api/jobs', headers=H).json()['jobs'])


def test_cancel_retry_delete(client):
    first = client.post('/api/jobs?name=a.png', content=png(), headers=H).json()
    second = client.post('/api/jobs?name=b.webp', content=png(fmt='WEBP'), headers=H).json()
    assert client.post(f'/api/jobs/{second["id"]}/cancel', headers=H).json()['status'] == 'cancelled'
    assert wait(client, first['id'])['status'] == 'done'
    assert client.get(f'/api/jobs/{second["id"]}/svg', headers=H).status_code == 409

    again = client.post(f'/api/jobs/{first["id"]}/retry?preset=logo', headers=H)
    assert again.status_code == 201 and again.json()['preset'] == 'logo'
    assert wait(client, again.json()['id'])['status'] == 'done'

    assert client.delete(f'/api/jobs/{first["id"]}', headers=H).status_code == 200
    assert client.get(f'/api/jobs/{first["id"]}', headers=H).status_code == 404
    assert client.delete(f'/api/jobs/{first["id"]}', headers=H).status_code == 404


def test_on_stage_reports_progress():
    from pngsvg import vectorize
    seen = []
    vectorize(Image.open(io.BytesIO(png())), on_stage=lambda name, f: seen.append(name))
    assert seen == ['ink', 'regions', 'curves', 'svg']
