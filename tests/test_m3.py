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
