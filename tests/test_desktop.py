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


def bridge(jobs, answers: dict, prefs_dir=None) -> Bridge:
    b = Bridge(jobs, server, prefs_dir=prefs_dir)
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
    b.set_close_message('Masih ada {n} foto. Tutup?')
    b.set_close_message('no placeholder')  # ignored: must contain {n}
    b._on_closing(w)
    assert w.confirm_close is True and w.localization['global.quitConfirmation'] == 'Masih ada 1 foto. Tutup?'
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


def test_save_folder_preferences_and_direct_save(jobs, tmp_path):
    prefs_dir = tmp_path / 'prefs'
    prefs_dir.mkdir()
    out = tmp_path / 'out'
    out.mkdir()
    b = bridge(jobs, {'FOLDER': str(out)}, prefs_dir=prefs_dir)
    assert b.get_prefs()['save_dir'] is None and b.get_prefs()['ask_each_time'] is True
    assert b.choose_save_dir()['save_dir'] == str(out)
    b.set_pref('ask_each_time', False)
    b.set_pref('save_dir', 'C:/elsewhere')  # not settable from the page
    again = Bridge(jobs, server, prefs_dir=prefs_dir).get_prefs()
    assert again['save_dir'] == str(out) and again['ask_each_time'] is False, 'remembered between runs'

    j = jobs.submit('scene.png', png_bytes(), 120, 90, 'logo', {})
    wait_done(jobs, j.id)
    jobs.name_pattern, jobs.size_attrs = '{name}-{style}', True
    try:
        def no_dialog(kind, **kw):
            raise AssertionError('no dialog when not asking')
        b._dialog = no_dialog
        assert b.save_svg(j.id) is True and b.save_svg(j.id) is True
        assert b.save_all([j.id]) == 1
    finally:
        jobs.name_pattern, jobs.size_attrs = '{name}', False
    names = sorted(p.name for p in out.iterdir())
    assert names == ['scene-logo-2.svg', 'scene-logo-3.svg', 'scene-logo.svg']
    assert (out / 'scene-logo.svg').read_text(encoding='utf-8').startswith('<svg width="120" height="90"')

    assert b.clear_save_dir()['save_dir'] is None


def test_broken_prefs_file_means_defaults(tmp_path):
    from pngsvg_app.desktop import load_prefs
    (tmp_path / 'settings.json').write_text('{not json', encoding='utf-8')
    assert load_prefs(tmp_path) == {'save_dir': None, 'ask_each_time': True, 'log': True}
    (tmp_path / 'settings.json').write_text('{"save_dir": "Z:/missing", "log": "yes"}', encoding='utf-8')
    assert load_prefs(tmp_path)['save_dir'] is None and load_prefs(tmp_path)['log'] is True


def test_open_url_only_allows_the_project(jobs, monkeypatch):
    import webbrowser
    opened = []
    monkeypatch.setattr(webbrowser, 'open', lambda url: opened.append(url) or True)
    b = bridge(jobs, {})
    assert b.open_url('https://example.com/phish') is False
    assert b.open_url('https://github.com/RidhuanDEV/png-to-svg-vectorize/releases') is True
    assert opened == ['https://github.com/RidhuanDEV/png-to-svg-vectorize/releases']


def test_save_other_formats_and_rendered_png(jobs, tmp_path):
    import base64
    j = jobs.submit('scene.png', png_bytes(), 120, 90, 'cartoon', {})
    wait_done(jobs, j.id)
    assert bridge(jobs, {'SAVE': str(tmp_path / 'print')}).save_svg(j.id, 'pdf') is True
    assert (tmp_path / 'print.pdf').read_bytes().startswith(b'%PDF')
    assert bridge(jobs, {'SAVE': str(tmp_path / 'x')}).save_svg(j.id, 'exe') is False
    folder = tmp_path / 'dxf'
    folder.mkdir()
    assert bridge(jobs, {'FOLDER': str(folder)}).save_all([j.id, j.id], 'dxf') == 2
    assert sorted(p.name for p in folder.iterdir()) == ['scene-2.dxf', 'scene.dxf']

    data = base64.b64encode(png_bytes()).decode()
    assert bridge(jobs, {'SAVE': str(tmp_path / 'big')}).save_png('scene.png', data) is True
    assert (tmp_path / 'big.png').read_bytes() == png_bytes()
    not_png = base64.b64encode(b'MZ\x90\x00 not a png').decode()
    assert bridge(jobs, {'SAVE': str(tmp_path / 'bad')}).save_png('scene.png', not_png) is False
    assert bridge(jobs, {'SAVE': str(tmp_path / 'bad')}).save_png('scene.png', '%%%') is False


def test_save_profile_validates(jobs, tmp_path):
    good = '{"format":"pngsvg-profile","version":1,"name":"Brand","preset":"logo","options":{"max_colors":4}}'
    assert bridge(jobs, {'SAVE': str(tmp_path / 'brand.pngsvg-profile.json')}).save_profile('Brand', good) is True
    assert (tmp_path / 'brand.pngsvg-profile.json').read_text(encoding='utf-8') == good
    assert bridge(jobs, {'SAVE': str(tmp_path / 'x')}).save_profile('x', '{"format":"other"}') is False
