"""Flat logo engine (preset 'logo' / 'pixel'): clean, small, one path per shape.

Fixtures (tests/fixtures):
- turion-logo.png: the Turion logo as designed (two blues + navy, slightly rounded corners) rendered with
  anti-aliasing on an off-white 1254 x 1254 canvas, like the original export.
- turion-logo-degraded.png: the same logo as an older trace drew it (wavy edges, light halos): robustness only.
"""
import math
import re
import time
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

from pngsvg import options_for, vectorize
from pngsvg.color import delta_e2000, to_lab
from pngsvg.export import _flatten, parse_svg
from pngsvg.logo import LogoParams, vectorize_logo

FIX = Path(__file__).parent / 'fixtures'
CMD = re.compile(r'[MLHVCQZmlhvcqz]')


def logo(name: str = 'turion-logo.png', **kw):
    return vectorize(Image.open(FIX / name), options_for('logo', **kw))


def paths(svg: str) -> list[tuple[str, str, str]]:
    """(id, fill, d) of every path."""
    return re.findall(r'<path id="([^"]+)" class="color-\d+" fill="(#[0-9A-F]{6})"(?: fill-rule="evenodd")? d="([^"]+)"', svg)


def rasterize(svg: str, crop, size: tuple[int, int], scale: int = 4) -> np.ndarray:
    """RGBA of the SVG placed back on the picture (crop = its x, y, w, h there), even-odd fill, 4x supersampled."""
    w, h = size
    canvas = np.zeros((h * scale, w * scale, 4), np.uint8)
    for shape in parse_svg(svg).shapes:
        mask = np.zeros((h * scale, w * scale), bool)
        for pts, _ in _flatten(shape.paths, tol=0.1):
            img = Image.new('1', (w * scale, h * scale), 0)
            ImageDraw.Draw(img).polygon([((x + crop[0]) * scale, (y + crop[1]) * scale) for x, y in pts], fill=1)
            mask ^= np.asarray(img)
        canvas[mask] = [*[round(c * 255) for c in shape.fill], 255]
    return np.asarray(Image.fromarray(canvas).resize((w, h), Image.Resampling.BOX))


def slanted_angles(svg: str) -> list[float]:
    """Directions (0-180 deg) of the straight sides that are neither horizontal nor vertical."""
    out = []
    for shape in parse_svg(svg).shapes:
        for (x0, y0), segs, _ in shape.paths:
            prev = (x0, y0)
            for s in segs:
                end = s[-1]
                if s[0] == 'L':
                    dx, dy = end[0] - prev[0], end[1] - prev[1]
                    a = math.degrees(math.atan2(dy, dx)) % 180
                    if math.hypot(dx, dy) > 40 and 5 < a < 175 and abs(a - 90) > 5:
                        out.append(a)
                prev = end
    return out


# ------------------------------------------------------------------------------------------------- the Turion logo

def test_turion_logo_is_four_clean_shapes():
    r = logo()
    svg = r.svg
    found = paths(svg)
    assert len(found) == 4, svg
    assert '<rect' not in svg and 'Gradient' not in svg and 'stroke' not in svg
    assert len(svg.encode()) < 2048
    assert sorted({f for _, f, _ in found}) == ['#01255B', '#029CF8']
    for _, _, d in found:
        commands = CMD.findall(d)
        assert len(commands) <= 8, d
        assert not set(commands) & set('CcQq'), f'straight sides only: {d}'
    assert [i for i, _, _ in found] == ['shape-0-0', 'shape-1-1', 'shape-0-2', 'shape-1-3']   # top-left first
    vb = [float(v) for v in re.search(r'viewBox="([^"]+)"', svg).group(1).split()]
    assert vb[:2] == [0, 0] and abs(vb[2] - 788) <= 3 and abs(vb[3] - 730) <= 3, 'trimmed to the logo'
    assert r.crop is not None and abs(r.crop[0] - 223) <= 3 and abs(r.crop[1] - 292) <= 3


def test_parallel_sides_share_one_angle():
    angles = slanted_angles(logo().svg)
    assert len(angles) >= 8
    for centre in (37.6, 142.4):
        group = [a for a in angles if abs(a - centre) < 5]
        assert group, centre
        assert max(group) - min(group) <= 0.5, group


def test_fidelity_iou_and_color():
    src = Image.open(FIX / 'turion-logo.png').convert('RGB')
    r = logo()
    out = rasterize(r.svg, r.crop, src.size)
    rgb = np.asarray(src, np.float64)
    pal = {'#01255B': (1, 37, 91), '#029CF8': (2, 156, 248)}
    lab_src = to_lab(rgb)
    # what the picture shows: nearest of background / navy / blue
    refs = np.array([[253, 254, 254], *pal.values()], np.float64)
    truth = np.argmin(np.linalg.norm(lab_src[..., None, :] - to_lab(refs)[None, None], axis=-1), axis=-1)
    alpha = out[..., 3] >= 128
    got = np.where(alpha, 1 + np.argmin(np.linalg.norm(out[..., None, :3].astype(np.float64) - refs[None, None, 1:], axis=-1), axis=-1), 0)
    for k in (1, 2):
        inter = np.logical_and(truth == k, got == k).sum()
        union = np.logical_or(truth == k, got == k).sum()
        assert inter / union >= 0.98, (k, inter / union)
    # color away from edges (2 px): rendered over the picture's background
    edge = np.zeros(truth.shape, bool)
    edge[:, 1:] |= truth[:, 1:] != truth[:, :-1]
    edge[1:] |= truth[1:] != truth[:-1]
    from scipy import ndimage
    inside = ~ndimage.binary_dilation(edge, iterations=2)
    shown = np.where(alpha[..., None], out[..., :3], np.array([253, 254, 254]))
    de = delta_e2000(to_lab(shown[inside].astype(np.float64)), lab_src[inside])
    assert float(de.mean()) < 3, float(de.mean())


def test_degraded_trace_is_still_clean():
    r = logo('turion-logo-degraded.png')
    assert 3 <= len(paths(r.svg)) <= 4 and len(r.palette) == 2
    assert '<rect' not in r.svg and 'Gradient' not in r.svg and 'stroke' not in r.svg
    assert len(r.svg.encode()) < 2048


def test_corner_radius_and_color_groups():
    r = logo(layers=True)
    assert re.search(r'<g id="color-0">.*<g id="color-1">', r.svg)
    rounded = vectorize(Image.open(FIX / 'turion-logo.png'), options_for('logo')).svg
    p = LogoParams(corner_radius=8, title='Turion', name='turion-logo')
    svg = vectorize_logo(Image.open(FIX / 'turion-logo.png'), p).svg
    assert svg.count('Q') + svg.count('q') >= 12 and '<title>Turion</title>' in svg and 'id="turion-logo"' in svg
    assert len(svg) > len(rounded)


def test_deterministic_and_fast():
    img = Image.open(FIX / 'turion-logo.png')
    t = time.perf_counter()
    a = vectorize(img, options_for('logo')).svg
    took = time.perf_counter() - t
    b = vectorize(img, options_for('logo')).svg
    assert a == b
    assert took < 10, took          # ~1.4 s on the development laptop (target 1.5 s); CI machines vary


# ---------------------------------------------------------------------------------------------- other pictures

def antialiased(draw, size=(480, 360), factor=4, background=(255, 255, 255)) -> Image.Image:
    big = Image.new('RGB', (size[0] * factor, size[1] * factor), background)
    draw(ImageDraw.Draw(big), factor)
    return big.resize(size, Image.Resampling.BOX)


def test_holes_stay_transparent():
    def draw(d, f):
        d.ellipse((60 * f, 40 * f, 300 * f, 280 * f), fill=(200, 30, 60))          # an "O"
        d.ellipse((120 * f, 100 * f, 240 * f, 220 * f), fill='white')
        d.polygon([(340 * f, 300 * f), (390 * f, 60 * f), (440 * f, 300 * f)], fill=(20, 40, 120))   # an "A"
        d.polygon([(370 * f, 240 * f), (390 * f, 150 * f), (410 * f, 240 * f)], fill='white')
    img = antialiased(draw)
    r = vectorize(img, options_for('logo'))
    found = paths(r.svg)
    assert len(found) == 2 and r.svg.count('fill-rule="evenodd"') == 2
    out = rasterize(r.svg, r.crop, img.size)
    assert out[160, 180, 3] == 0, 'the hole of the O is transparent'
    assert out[200, 390, 3] == 0, 'the hole of the A is transparent'
    assert out[60, 180, 3] == 255 and out[280, 360, 3] == 255
    o = next(d for i, f, d in found if f.startswith('#C'))
    assert 'L' not in o.upper().replace('LL', ''), 'a circle is curves, not a polygon'


def test_transparent_png_uses_alpha():
    img = Image.new('RGBA', (300, 200), (0, 0, 0, 0))
    ImageDraw.Draw(img).rectangle((40, 30, 260, 170), fill=(255, 255, 255, 255))     # a WHITE shape on transparency
    r = vectorize(img, options_for('logo'))
    assert len(paths(r.svg)) == 1 and '#FFFFFF' in r.svg
    assert r.crop == (40.0, 30.0, 221.0, 141.0)
    assert 'd="M0 0H221V141H0Z"' in r.svg or 'd="M221 0V141H0V0Z"' in r.svg or len(CMD.findall(paths(r.svg)[0][2])) <= 6


def test_shaded_picture_warns_and_is_limited():
    y, x = np.mgrid[0:200, 0:300]
    rgb = np.stack([x * 0.8, y * 1.2, (x + y) * 0.4], -1)
    img = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8))
    r = vectorize(img, options_for('logo'))
    assert r.warnings and 'not a flat logo' in r.warnings[0]
    assert len(r.palette) <= 8
    four = vectorize(img, options_for('logo', max_colors=4))
    assert len(four.palette) <= 4


def test_palette_is_forced():
    r = logo(palette=('#000080', '#00AAFF'))
    assert sorted({f for _, f, _ in paths(r.svg)}) == ['#000080', '#00AAFF']


def test_pixel_art_follows_the_grid():
    img = Image.new('RGB', (16, 16), 'white')
    d = ImageDraw.Draw(img)
    d.rectangle((3, 3, 12, 6), fill=(230, 60, 40))
    d.rectangle((5, 7, 8, 13), fill=(40, 60, 200))
    r = vectorize(img, options_for('pixel'))
    assert len(paths(r.svg)) == 2
    for _, _, d in paths(r.svg):
        assert set(CMD.findall(d)) <= set('MHVhvZ'), d
        assert all(float(v) == int(float(v)) for v in re.findall(r'-?\d*\.?\d+', d)), 'whole pixels'


def test_logo_preset_through_the_service_records_the_crop(tmp_path):
    pytest.importorskip('fastapi')
    from fastapi.testclient import TestClient

    from pngsvg_app import server
    from pngsvg_app.jobs import JobManager
    jobs = JobManager(workers=1)
    jobs.start()
    try:
        app = server.create_app(jobs, 't', {'testserver'}, static_dir=tmp_path)
        with TestClient(app) as c:
            data = (FIX / 'turion-logo.png').read_bytes()
            jid = c.post('/api/jobs?name=logo.png&preset=logo&options={"corner_radius":4}', content=data,
                         headers={'X-Token': 't'}).json()['id']
            end = time.time() + 120
            while time.time() < end:
                j = c.get(f'/api/jobs/{jid}', headers={'X-Token': 't'}).json()
                if j['status'] in ('done', 'error'):
                    break
                time.sleep(0.1)
            assert j['status'] == 'done' and j['stats']['regions'] == 4
            assert abs(j['stats']['crop'][2] - 788) <= 3 and j['stats']['warnings'] == []
            pdf = c.get(f'/api/jobs/{jid}/export?format=pdf', headers={'X-Token': 't'})
            assert pdf.content.startswith(b'%PDF')
    finally:
        jobs.shutdown()
