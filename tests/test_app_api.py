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


# -- M7: workbench (staged) → queue, speed settings ------------------------------------------------------------

def test_staged_images_wait_until_started(client):
    a = client.post('/api/jobs?name=a.png&start=false', content=png(), headers=H).json()
    b = client.post('/api/jobs?name=b.png&start=false', content=png(), headers=H).json()
    assert a['status'] == b['status'] == 'staged'
    time.sleep(0.5)
    assert client.get(f'/api/jobs/{a["id"]}', headers=H).json()['status'] == 'staged', 'not processed by itself'
    r = client.post('/api/jobs/start', json={'ids': [b['id'], 'missing'], 'preset': 'logo',
                                             'options': {'tolerance': 0.4}}, headers=H)
    assert r.status_code == 200 and [j['id'] for j in r.json()['jobs']] == [b['id']]
    done = wait(client, b['id'])
    assert done['status'] == 'done' and done['preset'] == 'logo' and done['options'] == {'tolerance': 0.4}
    assert client.get(f'/api/jobs/{a["id"]}', headers=H).json()['status'] == 'staged', 'unselected photo untouched'
    again = client.post('/api/jobs/start', json={'ids': [b['id']]}, headers=H).json()
    assert again['jobs'] == [], 'a finished job is not started twice'


def test_start_validates_settings(client):
    a = client.post('/api/jobs?name=a.png&start=false', content=png(), headers=H).json()
    assert client.post('/api/jobs/start', json={'ids': [a['id']], 'preset': 'nope'}, headers=H).status_code == 422
    bad = {'ids': [a['id']], 'options': {'tolerance': 99}}
    assert client.post('/api/jobs/start', json=bad, headers=H).status_code == 422
    assert client.post('/api/jobs/start', json={'ids': []}, headers=H).status_code == 422
    assert client.get(f'/api/jobs/{a["id"]}', headers=H).json()['status'] == 'staged'


def test_workbench_limit(client, jobs, monkeypatch):
    staged = sum(1 for j in client.get('/api/jobs', headers=H).json()['jobs'] if j['status'] == 'staged')
    monkeypatch.setattr(jobs, 'max_staged', staged + 1)
    assert client.post('/api/jobs?name=x.png&start=false', content=png(), headers=H).status_code == 201
    r = client.post('/api/jobs?name=y.png&start=false', content=png(), headers=H)
    assert r.status_code == 409 and 'workbench' in r.json()['detail']


def test_settings_speed(client):
    s = client.get('/api/settings', headers=H).json()
    assert s['speed'] in ('auto', 'saver', 'balanced', 'fast') and s['concurrency'] >= 1
    assert set(s['speeds']) == {'saver', 'balanced', 'fast'} and s['speeds']['saver'] == 1
    r = client.put('/api/settings', json={'speed': 'saver'}, headers=H)
    assert r.status_code == 200 and r.json()['speed'] == 'saver'
    assert client.put('/api/settings', json={'speed': 'turbo'}, headers=H).status_code == 422
    client.put('/api/settings', json={'speed': 'auto'}, headers=H)


def test_auto_speed_and_concurrency_rules():
    from pngsvg_app.jobs import auto_speed, concurrency_for
    assert auto_speed(4, 8) == 'saver'
    assert auto_speed(8, None) == 'saver', 'unknown memory is treated as a weak machine'
    assert auto_speed(8, 16) == 'balanced'
    assert [concurrency_for(s, 2) for s in ('saver', 'balanced', 'fast')] == [1, 1, 1]
    assert [concurrency_for(s, 8) for s in ('saver', 'balanced', 'fast')] == [1, 2, 4]


def test_queue_runs_one_at_a_time_in_order_and_cancels_waiting(client):
    ids = [client.post(f'/api/jobs?name={i}.png&start=false', content=png((480, 360)), headers=H).json()['id']
           for i in range(3)]
    client.post('/api/jobs/start', json={'ids': ids}, headers=H)
    snap = {j['id']: j for j in client.get('/api/jobs', headers=H).json()['jobs']}
    running = [i for i in ids if snap[i]['status'] == 'running']
    assert len(running) <= 1, 'fixture manager runs one job at a time'
    queued = [snap[i] for i in ids if snap[i]['status'] == 'queued']
    assert [q['position'] for q in queued] == list(range(1, len(queued) + 1))
    last = ids[-1]
    if snap[last]['status'] == 'queued':
        assert client.post(f'/api/jobs/{last}/cancel', headers=H).json()['status'] == 'cancelled'
    for i in ids[:-1]:
        assert wait(client, i)['status'] == 'done'
    assert client.get(f'/api/jobs/{last}', headers=H).json()['status'] in ('cancelled', 'done')


def test_cancel_all_stops_waiting_work(client):
    ids = [client.post(f'/api/jobs?name=c{i}.png&start=false', content=png((480, 360)), headers=H).json()['id']
           for i in range(3)]
    client.post('/api/jobs/start', json={'ids': ids}, headers=H)
    stopped = client.post('/api/queue/cancel', headers=H).json()['cancelled']
    assert set(stopped) <= set(ids) and stopped
    for i in ids:
        assert wait(client, i)['status'] in ('cancelled', 'done')


# -- M8: output settings, limits, update check ------------------------------------------------------------------

def test_settings_change_one_field_at_a_time(client):
    before = client.get('/api/settings', headers=H).json()
    r = client.put('/api/settings', json={'name_pattern': '{nama}-{gaya}', 'size_attrs': True}, headers=H)
    s = r.json()
    assert r.status_code == 200 and s['name_pattern'] == '{nama}-{gaya}' and s['size_attrs'] is True
    assert s['speed'] == before['speed'], 'speed untouched'
    for bad in ({'max_side': 100}, {'max_staged': 0}, {'name_pattern': ''}, {'colour': 'red'}):
        assert client.put('/api/settings', json=bad, headers=H).status_code == 422, bad
    client.put('/api/settings', json={'name_pattern': '{name}', 'size_attrs': False}, headers=H)


def test_saved_names_and_size_follow_the_settings(client):
    job = client.post('/api/jobs?name=foto%20kucing.png&preset=logo', content=png(), headers=H).json()
    assert job['filename'] == 'foto kucing.svg'
    wait(client, job['id'])
    client.put('/api/settings', json={'name_pattern': '{name}-{style}', 'size_attrs': True}, headers=H)
    try:
        assert client.get(f'/api/jobs/{job["id"]}', headers=H).json()['filename'] == 'foto kucing-logo.svg'
        r = client.get(f'/api/jobs/{job["id"]}/svg?download=true', headers=H)
        assert 'foto%20kucing-logo.svg' in r.headers['content-disposition']
        assert r.text.startswith('<svg width="160" height="120"')
        z = zipfile.ZipFile(io.BytesIO(client.get(f'/api/export.zip?ids={job["id"]}', headers=H).content))
        assert z.namelist() == ['foto kucing-logo.svg']
        assert z.read('foto kucing-logo.svg').decode().startswith('<svg width="160"')
    finally:
        client.put('/api/settings', json={'name_pattern': '{name}', 'size_attrs': False}, headers=H)
    assert client.get(f'/api/jobs/{job["id"]}/svg', headers=H).text.startswith('<svg xmlns=')


def test_largest_photo_setting(client):
    client.put('/api/settings', json={'max_side': 500}, headers=H)
    try:
        r = client.post('/api/jobs?name=big.png&start=false', content=png((640, 480)), headers=H)
        assert r.status_code == 413 and '500 px' in r.json()['detail']
    finally:
        client.put('/api/settings', json={'max_side': 8000}, headers=H)
    assert client.post('/api/jobs?name=big.png&start=false', content=png((640, 480)), headers=H).status_code == 201


def test_coordinate_precision_option(client):
    import re as _re
    a = client.post('/api/jobs?name=a.png&preset=cartoon&options=' + json.dumps({'decimals': 0}), content=png(),
                    headers=H).json()
    b = client.post('/api/jobs?name=b.png&preset=cartoon&options=' + json.dumps({'decimals': 2}), content=png(),
                    headers=H).json()
    sa = client.get(f'/api/jobs/{wait(client, a["id"])["id"]}/svg', headers=H).text
    sb = client.get(f'/api/jobs/{wait(client, b["id"])["id"]}/svg', headers=H).text

    def paths(s):
        return ' '.join(_re.findall(r' d="([^"]+)"', s))
    assert '.' not in paths(sa), 'no decimals in path data'
    assert _re.search(r'\.\d\d', paths(sb)), 'two decimals used'
    assert len(sa) < len(sb)
    bad = client.post('/api/jobs?name=c.png&options=' + json.dumps({'decimals': 5}), content=png(), headers=H)
    assert bad.status_code == 422


def test_update_check(client, monkeypatch):
    import urllib.error

    from pngsvg_app import server as srv

    class Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    calls = []

    def fake(payload=None, error=None):
        def opener(req, timeout):
            calls.append(req.full_url)
            if error:
                raise error
            return Resp(json.dumps(payload).encode())
        return opener

    monkeypatch.setattr(srv.urllib.request, 'urlopen',
                        fake({'tag_name': 'v99.0.0', 'html_url': 'https://github.com/x/y/releases/v99'}))
    r = client.get('/api/update', headers=H).json()
    assert r['newer'] is True and r['latest'] == '99.0.0' and r['url'].startswith('https://github.com/')
    assert calls == [srv.LATEST_RELEASE_URL]

    monkeypatch.setattr(srv.urllib.request, 'urlopen', fake({'tag_name': 'v0.1.0', 'html_url': 'javascript:x'}))
    r = client.get('/api/update', headers=H).json()
    assert r['newer'] is False and r['url'] is None, 'only https://github.com links are passed on'

    monkeypatch.setattr(srv.urllib.request, 'urlopen',
                        fake(error=urllib.error.HTTPError(srv.LATEST_RELEASE_URL, 404, 'nf', {}, None)))
    assert client.get('/api/update', headers=H).json() == {'current': srv.pngsvg.__version__, 'latest': None,
                                                           'newer': False, 'url': None}
    monkeypatch.setattr(srv.urllib.request, 'urlopen', fake(error=urllib.error.URLError('offline')))
    assert client.get('/api/update', headers=H).status_code == 502


def test_output_name_rules():
    import datetime as dt

    from pngsvg_app.server import output_name
    d = dt.date(2026, 10, 18)
    assert output_name('a.png', 'logo', '{tanggal}_{nama}', d) == '2026-10-18_a.svg'
    assert output_name('a.png', 'logo', '../../{name}', d) == 'a.svg', 'no path traversal'
    assert output_name('a.png', 'logo', 'x:y*z', d) == 'x-y-z.svg'
    assert output_name('a.png', 'logo', '{oops}', d) == '{oops}.svg', 'unknown braces stay literal'
