import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pytest
from PIL import Image, ImageDraw

from pngsvg import PRESETS, options_for, vectorize
from pngsvg.core import _fit_all
from pngsvg.curves import _midpoints, fit_chain
from pngsvg.planar import build_chains, subpixel_offsets


def _scene(size=(200, 150)) -> Image.Image:
    img = Image.new('RGB', size, (240, 244, 250))
    d = ImageDraw.Draw(img)
    d.ellipse((30, 20, 120, 110), fill=(37, 99, 235), outline=(15, 23, 42), width=4)
    d.rectangle((110, 60, 180, 130), fill=(245, 158, 11))
    return img


@pytest.mark.parametrize('preset', list(PRESETS))
def test_every_preset_gives_pure_svg(preset):
    res = vectorize(_scene(), options_for(preset, id_prefix='t'))
    root = ET.fromstring(res.svg)
    tags = {el.tag.split('}')[-1] for el in root.iter()}
    assert tags <= {'svg', 'defs', 'linearGradient', 'radialGradient', 'stop', 'g', 'rect', 'path'}


def test_unknown_preset_is_rejected():
    with pytest.raises(ValueError):
        options_for('nope')


def test_ball_gets_one_radial_gradient():
    w, h = 240, 200
    yy, xx = np.mgrid[0:h, 0:w]
    t = np.clip(np.hypot(xx - 100, yy - 80) / 110, 0, 1)[..., None]
    ball = (np.array([186, 230, 253]) * (1 - t) + np.array([37, 99, 235]) * t)
    inside = (np.hypot(xx - 120, yy - 100) < 80)[..., None]
    rgb = np.where(inside, ball, np.array([236, 242, 252])).astype(np.uint8)
    res = vectorize(Image.fromarray(rgb))
    # the inside of the ball is one radial region (without the M3 radial growth it is ~10 concentric bands);
    # thin crescents along the hard, un-anti-aliased edge may stay separate
    assert 1 <= res.svg.count('<radialGradient') <= 3
    assert res.regions <= 6


def test_subpixel_offset_finds_fractional_edge():
    label = np.ones((12, 20), int)
    label[:, 10:] = 2
    A, B = np.array([255.0, 0, 0]), np.array([0.0, 0, 255])
    rgb = np.where((label == 1)[..., None], A, B)
    rgb[:, 10] = 0.3 * A + 0.7 * B                       # true edge at x = 10.3
    mean = np.array([[0, 0, 0], A, B])
    chain = next(c for c in build_chains(label) if {c.left, c.right} == {1, 2})
    off = subpixel_offsets(chain, label, rgb, mean, None)
    mids = _midpoints(chain.points, chain.closed, off)
    inner = mids[(mids[:, 1] > 2) & (mids[:, 1] < 10)]
    assert np.allclose(inner[:, 0], 10.3, atol=0.05)


def test_parallel_fit_matches_serial():
    label = np.zeros((60, 80), int)
    label[10:50, 10:70] = 1
    label[20:40, 30:50] = 2
    jobs = [(c.points, c.closed, 1.0, 0.5, 4, 55.0, None) for c in build_chains(label)] * 30
    serial = _fit_all(jobs, None)
    with ThreadPoolExecutor(4) as ex:
        par = _fit_all(jobs, ex, min_parallel=0)
    assert len(serial) == len(par)
    assert all(len(a) == len(b) and all(np.allclose(x, y) for x, y in zip(a, b)) for a, b in zip(serial, par))
    assert fit_chain(*jobs[0][:6])                       # positional API still works without offsets


def test_transparent_png_is_flattened_on_white():
    from pngsvg.core import flatten
    img = Image.new('RGBA', (60, 40), (0, 0, 0, 0))                     # fully transparent black
    ImageDraw.Draw(img).ellipse((10, 5, 50, 35), fill=(37, 99, 235, 255))
    flat = np.asarray(flatten(img))
    assert tuple(flat[0, 0]) == (255, 255, 255) and tuple(flat[20, 30]) == (37, 99, 235)
    res = vectorize(img)
    assert '#FFFFFF' in res.svg.upper()                                   # white background, not black


def test_quality_metrics():
    from pngsvg.compare import edge_split, psnr, ssim
    a = Image.new('RGB', (64, 48), 'white')
    ImageDraw.Draw(a).rectangle((10, 10, 40, 30), fill=(200, 40, 40))
    assert psnr(a, a) == float('inf') and abs(ssim(a, a) - 1) < 1e-9
    b = a.copy()
    ImageDraw.Draw(b).rectangle((10, 10, 41, 30), fill=(200, 40, 40))        # one column off, on the edge
    assert 20 < psnr(a, b) < 40 and 0.8 < ssim(a, b) < 1
    flat, on_edges = edge_split(a, b)
    assert flat == 100.0 and on_edges == 100.0


def test_defect_area_counts_a_missing_shape_not_an_edge_shift():
    from pngsvg.compare import defect_area, similarity
    a = Image.new('RGB', (200, 200), 'white')
    ImageDraw.Draw(a).rectangle((40, 40, 160, 160), fill=(200, 40, 40))
    shifted = Image.new('RGB', (200, 200), 'white')
    ImageDraw.Draw(shifted).rectangle((41, 40, 161, 160), fill=(200, 40, 40))   # one column off: anti-aliasing scale
    assert defect_area(a, shifted) == 0.0
    missing = a.copy()
    ImageDraw.Draw(missing).rectangle((40, 40, 70, 70), fill='white')            # a 31x31 piece gone
    assert abs(defect_area(a, missing) - 100 * 31 * 31 / 200 ** 2) < 0.01
    assert similarity(a, missing)[0] > 98                                         # ...which the mean barely sees


def _outline_fills(svg: str) -> list[str]:
    import re
    group = re.search(r'<g id="outline"( fill="(#[0-9A-F]{6})")?>(.*?)</g>', svg)
    if group is None:
        return []
    return [group.group(2)] if group.group(2) else re.findall(r'fill="(#[0-9A-F]{6})"', group.group(3))


def test_grey_lines_keep_their_own_ink():
    # one ink color per picture turned thin grey lines into thinner black ones; each stroke now has its ink
    img = Image.new('RGB', (480, 360), 'white')
    d = ImageDraw.Draw(img)
    d.ellipse((40, 40, 300, 300), fill=(250, 200, 160), outline=(15, 15, 15), width=6)
    for i in range(4):
        d.line((320, 60 + 60 * i, 460, 80 + 60 * i), fill=(128, 128, 128), width=3)
    inks = _outline_fills(vectorize(img).svg)
    assert len(inks) == 2
    greys = [int(c[1:3], 16) for c in inks]
    assert min(greys) < 40 and 100 < max(greys) < 160


def test_a_shaded_dark_area_is_a_fill_but_a_flat_one_stays_ink():
    from pngsvg.compare import defect_area
    yy, xx = np.mgrid[0:300, 0:400]
    screen = np.full((300, 400, 3), 255.0)
    inside = (xx > 60) & (xx < 340) & (yy > 40) & (yy < 260)
    screen[inside] = 8
    glare = inside & (yy < 140 - 0.3 * (xx - 60))                   # a dark-grey reflection on the black screen
    screen[glare] = 34
    img = Image.fromarray(screen.astype(np.uint8))
    from pngsvg.compare import render
    out = render(vectorize(img).svg, 400, 300)
    if out is None:
        pytest.skip('no Chrome/Edge to render with')
    assert defect_area(img, out) < 0.5                                # the reflection is kept
    flat = Image.new('RGB', (400, 300), 'white')
    ImageDraw.Draw(flat).rectangle((60, 40, 340, 260), fill=(8, 8, 8))
    assert len(_outline_fills(vectorize(flat).svg)) == 1               # a flat black area is still drawn as ink
