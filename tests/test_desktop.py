"""Desktop bridge logic with the native dialogs stubbed out (no window, no pywebview needed)."""
import io
import time

import pytest
from PIL import Image, ImageDraw

pytest.importorskip('fastapi')

from pngsvg_app import server  # noqa: E402
from pngsvg_app.desktop import Bridge  # noqa: E402
from pngsvg_app.jobs import JobManager  # noqa: E402


def png_bytes() -> bytes:
    img = Image.new('RGB', (120, 90), (240, 244, 250))
    ImageDraw.Draw(img).ellipse((10, 10, 80, 80), fill=(37, 99, 235), outline=(15, 23, 42), width=3)
    buf = io.BytesIO()
    img.save(buf, 'PNG')
    return buf.getvalue()


@pytest.fixture(scope='module')
def jobs():
    m = JobManager(workers=1)
    m.start()
    yield m
    m.shutdown()


def bridge(jobs, answers: dict) -> Bridge:
    b = Bridge(jobs, server)
    b._dialog = lambda kind, **kw: answers.get(kind)
    return b


def wait_done(jobs, job_id):
    end = time.time() + 120
    while jobs.get(job_id).status not in ('done', 'error', 'cancelled'):
        assert time.time() < end, 'job did not finish'
        time.sleep(0.1)
    return jobs.get(job_id)


def test_open_files_stages_images_and_reports_bad_files(jobs, tmp_path):
    good = tmp_path / 'ball.png'
    good.write_bytes(png_bytes())
    bad = tmp_path / 'notes.png'
    bad.write_text('not an image')
    out = bridge(jobs, {'OPEN': [str(good), str(bad)]}).open_files()
    assert len(out['ids']) == 1 and len(out['errors']) == 1
    assert out['errors'][0]['name'] == 'notes.png' and out['errors'][0]['code'] == 415
    job = jobs.get(out['ids'][0])
    assert job.status == 'staged', 'nothing is processed until the user presses Process'
    jobs.start_jobs([job.id], 'logo', {'tolerance': 0.4})
    job = wait_done(jobs, job.id)
    assert job.status == 'done' and job.preset == 'logo' and job.options == {'tolerance': 0.4}


def test_close_asks_only_while_busy(jobs):
    class FakeWindow:
        confirm_close = False
        localization = {'global.quitConfirmation': ''}

    b = bridge(jobs, {})
    w = FakeWindow()
    b._on_closing(w)
    assert w.confirm_close is False
    j = jobs.submit('scene.png', png_bytes(), 120, 90, 'cartoon', {})
    b.set_lang('id')
    b._on_closing(w)
    assert w.confirm_close is True and 'foto' in w.localization['global.quitConfirmation']
    wait_done(jobs, j.id)


def test_cancelled_dialog_does_nothing(jobs):
    assert bridge(jobs, {}).open_files() == {'ids': [], 'errors': []}
    assert bridge(jobs, {}).save_all(['x']) == 0


def test_save_svg_and_save_all_never_overwrite(jobs, tmp_path):
    j = jobs.submit('scene.png', png_bytes(), 120, 90, 'cartoon', {})
    wait_done(jobs, j.id)
    target = tmp_path / 'chosen'
    assert bridge(jobs, {'SAVE': str(target)}).save_svg(j.id) is True
    assert (tmp_path / 'chosen.svg').read_text(encoding='utf-8').startswith('<svg')

    folder = tmp_path / 'all'
    folder.mkdir()
    (folder / 'scene.svg').write_text('keep me', encoding='utf-8')
    assert bridge(jobs, {'FOLDER': str(folder)}).save_all([j.id, 'missing']) == 1
    assert (folder / 'scene.svg').read_text(encoding='utf-8') == 'keep me'
    assert (folder / 'scene-2.svg').read_text(encoding='utf-8').startswith('<svg')
