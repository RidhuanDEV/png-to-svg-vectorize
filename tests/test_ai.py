"""Optional AI step: tiled inference, model download/verification, automatic rule, and the AI job path end to end.

A tiny ONNX "upscaler" (nearest x4) is built here, so the whole path is tested without downloading a real model.
"""
import hashlib
import http.server
import io
import threading
import time
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

ort = pytest.importorskip('onnxruntime')
onnx = pytest.importorskip('onnx')
pytest.importorskip('fastapi')
from fastapi.testclient import TestClient  # noqa: E402

from pngsvg import ai  # noqa: E402
from pngsvg_app import server  # noqa: E402
from pngsvg_app.jobs import JobManager, wants_ai  # noqa: E402
from pngsvg_app.models import ModelInfo, ModelStore  # noqa: E402

H = {'X-Token': 't'}


def tiny_x4_model(path: Path) -> Path:
    """input (1,3,h,w) float -> nearest-neighbour x4 output, named like the real models."""
    from onnx import TensorProto, helper
    scales = helper.make_tensor('scales', TensorProto.FLOAT, [4], [1.0, 1.0, 4.0, 4.0])
    node = helper.make_node('Resize', ['input', '', 'scales'], ['output'], mode='nearest')
    graph = helper.make_graph([node], 'x4', [helper.make_tensor_value_info('input', TensorProto.FLOAT, [1, 3, 'h', 'w'])],
                              [helper.make_tensor_value_info('output', TensorProto.FLOAT, [1, 3, 'H', 'W'])], [scales])
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid('', 17)])
    model.ir_version = 8
    onnx.save(model, path)
    return path


def picture(size=(150, 110)) -> Image.Image:
    img = Image.new('RGB', size, (240, 244, 250))
    d = ImageDraw.Draw(img)
    d.ellipse((15, 10, 90, 85), fill=(37, 99, 235), outline=(15, 23, 42), width=3)
    d.rectangle((80, 45, 140, 100), fill=(245, 158, 11))
    return img


def png_bytes(img) -> bytes:
    buf = io.BytesIO()
    img.save(buf, 'PNG')
    return buf.getvalue()


def test_tiled_upscale_matches_a_single_pass(tmp_path):
    model = tiny_x4_model(tmp_path / 'x4.onnx')
    img = picture((157, 93))  # not a multiple of the tile size
    out = ai.upscale(img, model, 'cpu', tile=48, overlap=6)
    assert out.size == (157 * 4, 93 * 4)
    ref = img.resize(out.size, Image.Resampling.NEAREST)
    assert np.array_equal(np.asarray(out), np.asarray(ref)), 'tiles are stitched without seams or shifts'
    assert ai.enhance(img, model, 'cpu', target=2).size == (314, 186)


def test_providers_always_end_with_cpu():
    assert ai.providers_for('cpu') == ['CPUExecutionProvider']
    assert ai.providers_for('auto')[-1] == 'CPUExecutionProvider'


def test_automatic_rule():
    jpeg = b'\xff\xd8\xff\xe0rest'
    assert wants_ai({'ai': 'illustration'}, b'png', 4000, 3000) is True
    assert wants_ai({'ai': 'illustration', 'ai_auto': True}, b'png', 4000, 3000) is False
    assert wants_ai({'ai': 'illustration', 'ai_auto': True}, b'png', 800, 600) is True
    assert wants_ai({'ai': 'illustration', 'ai_auto': True}, jpeg, 4000, 3000) is True
    assert wants_ai({}, jpeg, 10, 10) is False


@pytest.fixture()
def file_server(tmp_path):
    """Serves tmp_path/served over http://127.0.0.1:<port> (stands in for the GitHub release)."""
    root = tmp_path / 'served'
    root.mkdir()

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(root), **kw)

        def log_message(self, *a):
            pass

    httpd = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield root, f'http://127.0.0.1:{httpd.server_address[1]}'
    httpd.shutdown()


def store_for(root: Path, url: str, folder: Path, content: bytes, wrong_hash=False) -> ModelStore:
    (root / 'm.onnx').write_bytes(content)
    digest = hashlib.sha256(b'other' if wrong_hash else content).hexdigest()
    cat = {'m': ModelInfo('m', 'm.onnx', len(content), digest, 'test')}
    return ModelStore(folder, release=url, catalog=cat)


def wait_state(store: ModelStore, name: str, timeout=20):
    end = time.time() + timeout
    while time.time() < end:
        st = next(s for s in store.status() if s['name'] == name)
        if st['state'] != 'downloading':
            return st
        time.sleep(0.05)
    raise AssertionError('download did not finish')


def test_download_verifies_the_checksum(tmp_path, file_server):
    root, url = file_server
    content = bytes(range(256)) * 400
    good = store_for(root, url, tmp_path / 'models', content)
    assert good.path('m') is None and good.status()[0]['state'] == 'missing'
    good.download('m')
    st = wait_state(good, 'm')
    assert st['state'] == 'installed' and st['progress'] == 1.0
    assert good.path('m').read_bytes() == content
    good.remove('m')
    assert good.path('m') is None

    bad = store_for(root, url, tmp_path / 'models2', content, wrong_hash=True)
    bad.download('m')
    st = wait_state(bad, 'm')
    assert st['state'] == 'error' and st['error'] == 'checksum'
    assert list((tmp_path / 'models2').iterdir()) == [], 'a bad file is never kept'

    missing = ModelStore(tmp_path / 'models3', release=url + '/nothing-here',
                         catalog={'m': ModelInfo('m', 'm.onnx', 10, '0' * 64, 'x')})
    missing.download('m')
    assert wait_state(missing, 'm')['error'] == 'network'


@pytest.fixture()
def ai_service(tmp_path):
    jobs = JobManager(workers=1)
    jobs.models = ModelStore(tmp_path / 'models')
    jobs.start()
    model = tiny_x4_model(tmp_path / 'tiny.onnx')
    app = server.create_app(jobs, 't', {'testserver'}, static_dir=tmp_path)
    with TestClient(app) as c:
        yield c, jobs, model
    jobs.shutdown()


def wait_job(client, jid, timeout=120):
    end = time.time() + timeout
    while time.time() < end:
        j = client.get(f'/api/jobs/{jid}', headers=H).json()
        if j['status'] in ('done', 'error', 'cancelled'):
            return j
        time.sleep(0.2)
    raise AssertionError('job did not finish')


def test_ai_api_and_job(ai_service, monkeypatch):
    client, jobs, model = ai_service
    st = client.get('/api/ai', headers=H).json()
    assert st['runtime'] is True and {m['name'] for m in st['models']} == {'illustration', 'general'}
    assert all(m['state'] == 'missing' for m in st['models'])
    assert client.post('/api/ai/models/nope', headers=H).status_code == 404

    # asking for AI without the model is refused up front, in plain terms
    r = client.post('/api/jobs?name=a.png&options={"ai":"illustration"}', content=png_bytes(picture()), headers=H)
    assert r.status_code == 422 and 'not installed' in r.json()['detail']

    # pretend the illustration model is installed (the tiny x4 stand-in)
    monkeypatch.setattr(jobs.models, 'path', lambda name: model if name == 'illustration' else None)
    assert client.put('/api/settings', json={'ai_accel': 'cpu'}, headers=H).json()['ai_accel'] == 'cpu'
    plain = wait_job(client, client.post('/api/jobs?name=p.png', content=png_bytes(picture()), headers=H).json()['id'])
    j = client.post('/api/jobs?name=a.png&options={"ai":"illustration"}', content=png_bytes(picture()), headers=H)
    done = wait_job(client, j.json()['id'])
    assert done['status'] == 'done' and done['stats']['ai'] is True and plain['stats']['ai'] is False
    svg = client.get(f'/api/jobs/{done["id"]}/svg', headers=H).text
    assert 'viewBox="0 0 300 220"' in svg, 'traced at 2x the photo size'
    assert done['width'] == 150, 'the job keeps the photo size'

    # automatic: a big PNG skips the AI step
    big = picture((1200, 900))
    k = client.post('/api/jobs?name=big.png&options={"ai":"illustration","ai_auto":true}', content=png_bytes(big),
                    headers=H)
    assert wait_job(client, k.json()['id'])['stats']['ai'] is False
