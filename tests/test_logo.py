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
    assert len(r.palette) <= LogoParams().max_auto_colors
    four = vectorize(img, options_for('logo', max_colors=4))
    assert len(four.palette) <= 4


def test_opaque_dark_art_without_background_has_no_holes():
    # four dark quadrants: no border color dominates, so there is no background and nothing may turn transparent
    img = Image.new('RGB', (240, 160), (20, 24, 40))
    d = ImageDraw.Draw(img)
    d.rectangle((120, 0, 239, 79), fill=(60, 30, 30))
    d.rectangle((0, 80, 119, 159), fill=(30, 60, 40))
    d.rectangle((120, 80, 239, 159), fill=(200, 180, 90))
    d.ellipse((90, 50, 150, 110), fill=(22, 26, 42))           # art in (almost) the border color
    r = vectorize(img, options_for('logo'))
    assert r.crop == (0.0, 0.0, 240.0, 160.0)
    assert (rasterize(r.svg, r.crop, img.size)[..., 3] > 250).mean() > 0.99


def test_shaded_picture_keeps_its_dark_frame():
    # a dominant border color on a picture that is not flat is part of the art, not a background
    y, x = np.mgrid[0:200, 0:300]
    rgb = np.stack([x * 0.8, y * 1.2, (x + y) * 0.4], -1)
    rgb[:30], rgb[-30:], rgb[:, :30], rgb[:, -30:] = 12, 12, 12, 12
    img = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8))
    r = vectorize(img, options_for('logo'))
    assert any('background was kept' in w for w in r.warnings)
    assert (rasterize(r.svg, r.crop, img.size)[..., 3] > 250).mean() > 0.99


def test_a_smoothed_textured_gradient_keeps_its_border_color():
    # the texture is smoothed like noise, which makes the border color dominant; the gradient left is still not flat
    y, _ = np.mgrid[0:240, 0:360]
    rgb = np.stack([10 + y * 0.15, 15 + y * 0.2, 40 + y * 0.3], -1)
    rgb = rgb + np.random.default_rng(0).normal(0, 3, (240, 360, 3))
    img = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8))
    r = vectorize(img, options_for('logo'))
    assert any('gradient' in w for w in r.warnings) and any('background was kept' in w for w in r.warnings)
    assert (rasterize(r.svg, r.crop, img.size)[..., 3] > 250).mean() > 0.99


def test_two_shades_of_one_hue_stay_two_colors():
    # flat UI icons pair a color with its darker shade (here CIEDE2000 8.6 and 10): both are design colors
    img = Image.new('RGB', (400, 300), 'white')
    d = ImageDraw.Draw(img)
    d.rectangle((40, 40, 190, 260), fill=(231, 76, 60))
    d.rectangle((190, 40, 360, 260), fill=(192, 57, 43))
    d.rectangle((80, 100, 150, 200), fill=(52, 152, 219))
    d.rectangle((230, 100, 320, 200), fill=(41, 128, 185))
    r = vectorize(img, options_for('logo'))
    assert sorted(r.palette) == ['#2980B9', '#3498DB', '#C0392B', '#E74C3C']


def _icon_on_white() -> Image.Image:
    img = Image.new('RGB', (800, 600), 'white')
    d = ImageDraw.Draw(img)
    d.rectangle((300, 200, 500, 400), fill=(236, 240, 241))        # close to white (CIEDE2000 under 6)
    d.rectangle((320, 220, 400, 300), fill=(231, 76, 60))
    d.rectangle((400, 220, 480, 300), fill=(192, 57, 43))
    d.rectangle((320, 300, 400, 380), fill=(52, 152, 219))
    d.rectangle((400, 300, 480, 380), fill=(41, 128, 185))
    return img


def test_a_kept_background_does_not_crowd_out_the_colors():
    # the white background is most of the picture: the art's own colors are found without it, then white is added
    r = vectorize(_icon_on_white(), options_for('logo', remove_bg=False))
    assert sorted(r.palette) == ['#2980B9', '#3498DB', '#C0392B', '#E74C3C', '#ECF0F1', '#FFFFFF']
    removed = vectorize(_icon_on_white(), options_for('logo'))
    assert '#FFFFFF' not in removed.palette


def _noisy_flag(sigma: float) -> Image.Image:
    img = Image.new('RGB', (480, 320), (206, 17, 38))
    d = ImageDraw.Draw(img)
    d.rectangle((0, 107, 479, 213), fill=(255, 255, 255))
    d.ellipse((180, 100, 300, 220), fill=(0, 56, 147))
    noise = np.random.default_rng(1).normal(0, sigma, (320, 480, 3))
    return Image.fromarray(np.clip(np.asarray(img, np.float64) + noise, 0, 255).astype(np.uint8))


def test_noise_is_smoothed_away_and_a_clean_picture_is_untouched():
    from pngsvg.logo import noise_level
    assert noise_level(np.asarray(_noisy_flag(0), np.float64)) == 0.0
    r = vectorize(_noisy_flag(16), options_for('logo', remove_bg=False))
    assert len(r.palette) == 3 and not r.warnings
    pal = to_lab(np.array([[int(h[i:i + 2], 16) for i in (1, 3, 5)] for h in r.palette], np.float64))
    for want in ((206, 17, 38), (255, 255, 255), (0, 56, 147)):
        assert float(np.min(delta_e2000(pal, to_lab(np.array(want, np.float64))))) < 3
    assert r.regions <= 6


def test_light_halo_returns_to_the_background_but_a_light_line_stays():
    img = Image.new('RGB', (400, 300), 'white')
    d = ImageDraw.Draw(img)
    d.rectangle((60, 60, 220, 240), fill=(228, 244, 252))             # a 4 px light rim around the shape...
    d.rectangle((64, 64, 216, 236), fill=(2, 156, 248))
    d.rectangle((300, 40, 303, 260), fill=(228, 244, 252))            # ...and a light line on its own
    r = vectorize(img, options_for('logo'))
    assert sorted(r.palette) == ['#029CF8', '#E4F4FC']
    assert r.crop[0] == 64.0                                            # the rim is gone...
    assert [d for _, f, d in paths(r.svg) if f == '#E4F4FC'] == ['M240 0h-4V221h4Z']   # ...the line stays


@pytest.mark.parametrize('width', [4, 8])
def test_thin_bar_keeps_its_width(width):
    # 1.6.0 joined the two long sides of a thin bar at one point (parallel lines never meet): a zero-area sliver
    img = Image.new('RGB', (400, 300), 'white')
    ImageDraw.Draw(img).rectangle((300, 40, 300 + width - 1, 260), fill=(20, 20, 20))
    r = vectorize(img, options_for('logo'))
    assert paths(r.svg)[0][2] == f'M{width} 0H0V221H{width}Z' or paths(r.svg)[0][2] == f'M{width} 0h-{width}V221h{width}Z'


def test_rounded_bar_ends_stay_round():
    img = Image.new('RGB', (400, 300), 'white')
    ImageDraw.Draw(img).rounded_rectangle((300, 40, 315, 260), radius=8, fill=(20, 20, 20))
    d = paths(vectorize(img, options_for('logo')).svg)[0][2]
    assert d.count('c') + d.count('C') >= 2


def test_a_flat_grey_between_black_and_white_stays_grey():
    # 1.6: #545454 lies exactly on the black-white mix line, so the mix (anti-aliasing) won over the pure color
    img = Image.new('RGBA', (400, 300), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((40, 20, 360, 280), fill=(84, 84, 84, 255))
    d.ellipse((70, 50, 330, 250), fill=(41, 41, 41, 255))
    d.ellipse((150, 100, 250, 200), fill=(255, 255, 255, 255))
    r = vectorize(img, options_for('logo'))
    assert sorted(r.palette) == ['#292929', '#545454', '#FFFFFF']


def test_line_art_is_flat_but_a_gradient_is_not():
    lines = Image.new('RGB', (400, 300), 'white')
    d = ImageDraw.Draw(lines)
    for i in range(6):
        d.arc((20 + i * 30, 20, 380 - i * 30, 280), 10 * i, 300, fill='black', width=3)
    assert vectorize(lines, options_for('logo')).warnings == []
    y, x = np.mgrid[0:300, 0:400]
    whale = np.where((((x - 200) / 170) ** 2 + ((y - 150) / 120) ** 2 < 1)[..., None],
                     np.stack([40 + x * 0.1, 120 + y * 0.2, 150 + x * 0.12], -1), 255)
    r = vectorize(Image.fromarray(whale.astype(np.uint8)), options_for('logo'))
    assert r.warnings and ('gradient' in r.warnings[0] or 'shading' in r.warnings[0])


def test_pixel_art_keeps_every_color_and_every_pixel():
    img = Image.new('RGB', (32, 32), (105, 193, 235))
    px = img.load()
    for yy in range(8, 20):
        for xx in range(8, 20):
            px[xx, yy] = (0, 0, 0) if (xx + yy) % 2 else (249, 235, 170)        # a checkerboard: no pixel is "flat"
    px[25, 5] = (255, 255, 5)                                                    # a single-pixel star
    r = vectorize(img, options_for('pixel', remove_bg=False))
    assert sorted(r.palette) == ['#000000', '#69C1EB', '#F9EBAA', '#FFFF05']
    assert 'd="M25 5V6h1V5Z"' in r.svg                                          # the star, exactly one pixel
    from pngsvg.compare import find_browser, render
    if find_browser() is None:
        pytest.skip('no Chrome/Edge to render with')
    assert (np.asarray(render(r.svg, 32, 32)) == np.asarray(img)).all()        # every pixel as it was


def test_a_thin_ring_is_one_shape_and_stays_round():
    # 1.6 cut a 3 px ring into dozens of pieces (every thinner spot was taken for a neck between two shapes), so its
    # edges became short polygons; now it is one shape whose two edges are exact circles
    img = Image.new('RGB', (400, 400), 'white')
    ImageDraw.Draw(img).ellipse((50, 50, 350, 350), outline=(10, 10, 10), width=3)
    r = vectorize(img, options_for('logo'))
    assert len(paths(r.svg)) == 1
    d = paths(r.svg)[0][2]
    assert not re.search('[LlHhVv]', d) and len(CMD.findall(d)) <= 12               # 2 circles of 4 arcs


def test_an_ellipse_is_exact():
    img = Image.new('RGBA', (400, 300), (0, 0, 0, 0))
    ImageDraw.Draw(img).ellipse((60, 70, 340, 230), fill=(37, 99, 235, 255))
    r = vectorize(img, options_for('logo'))
    d = paths(r.svg)[0][2]
    assert len(CMD.findall(d)) <= 6                                                   # M + 4 cubics + Z
    out = rasterize(r.svg, r.crop, img.size)
    inside = np.asarray(img)[..., 3] > 128
    assert ((out[..., 3] > 128) == inside).mean() > 0.998


def test_a_gentle_curve_is_not_a_line():
    # the top edge bows by 0.7 px: inside the 1 px line tolerance, but the residual is systematic (an arc), so it
    # must stay a curve (1.6 drew it as a straight line)
    h, w, sub = 200, 400, 16
    x = np.arange(w) + 0.5
    edge = 100 - 0.7 * (1 - ((x - 200) / 200) ** 2)
    ys = np.arange(h * sub)[:, None] / sub
    cover = (ys > edge[None]).reshape(h, sub, w).mean(1)
    rgb = 255 - cover[..., None] * (255 - np.array([220, 60, 30]))
    r = vectorize(Image.fromarray(np.round(rgb).astype(np.uint8)), options_for('logo'))
    assert 'c' in paths(r.svg)[0][2].lower()


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
