import random
import re
import xml.etree.ElementTree as ET

import numpy as np
import pytest
from PIL import Image, ImageDraw

from pngsvg import Options, vectorize
from pngsvg.compare import find_browser, render, similarity
from pngsvg.pathdata import compact_path

_NUM = re.compile(r'[MmLlCcQqZz]|-?(?:\d+\.?\d*|\.\d+)')


def _absolute_points(d):
    """Parse an M/L/C/Q/Z path (absolute or relative) into absolute end/control points."""
    toks = _NUM.findall(d)
    pts, cx, cy, sx, sy, cmd, i = [], 0.0, 0.0, 0.0, 0.0, None, 0
    while i < len(toks):
        if toks[i].isalpha():
            cmd = toks[i]
            i += 1
        if cmd in 'zZ':
            cx, cy = sx, sy
            cmd = None
            continue
        n = {'m': 2, 'l': 2, 'c': 6, 'q': 4}[cmd.lower()]
        v = [float(x) for x in toks[i:i + n]]
        i += n
        rel = cmd.islower()
        p = [(v[k] + (cx if rel else 0), v[k + 1] + (cy if rel else 0)) for k in range(0, n, 2)]
        pts += p
        cx, cy = p[-1]
        if cmd in 'mM':
            sx, sy = p[-1]
            cmd = 'l' if rel else 'L'
    return np.array(pts)


def test_compact_path_round_trip():
    rng = random.Random(1)
    for _ in range(300):
        p = [(rng.uniform(-50, 900), rng.uniform(-50, 900)) for _ in range(13)]
        d = 'M%.3f %.3f' % p[0] + ''.join('C%.3f %.3f %.3f %.3f %.3f %.3f' % (p[k] + p[k + 1] + p[k + 2]) for k in (1, 4, 7, 10)) + 'Z'
        a, b = _absolute_points(d), _absolute_points(compact_path(d))
        assert a.shape == b.shape
        assert np.abs(a - b).max() <= 0.05 + 1e-6   # one rounding step, no accumulated drift


def test_compact_path_is_smaller():
    d = 'M697.5 658C698.1 660.3 699.4 662.8 702 665.2C704.5 666.6 706.7 668 708.7 672.7Z'
    assert len(compact_path(d)) < 0.8 * len(d)   # short sample; real files shrink ~50%


def _sample(w=360, h=240):
    """Cartoon-like test image: tinted background, gradient-shaded face with dark outline, blush, red mouth."""
    img = Image.new('RGB', (w, h), (225, 240, 230))
    px = img.load()
    for y in range(h):
        for x in range(w):
            if (x - 180) ** 2 / 90 ** 2 + (y - 120) ** 2 / 95 ** 2 <= 1:
                t = (x - 90) / 180
                px[x, y] = (int(250 - 20 * t), int(200 - 25 * t), int(150 - 30 * t))
    d = ImageDraw.Draw(img)
    d.ellipse([90, 25, 270, 215], outline=(15, 30, 45), width=6)
    d.ellipse([120, 120, 150, 140], fill=(240, 150, 140))
    d.chord([150, 140, 210, 185], 0, 180, fill=(170, 50, 55), outline=(15, 30, 45), width=4)
    d.ellipse([140, 85, 156, 101], fill=(15, 30, 45))
    d.ellipse([204, 85, 220, 101], fill=(15, 30, 45))
    return img


def test_output_is_pure_path_svg():
    res = vectorize(_sample(), Options(id_prefix='test'))
    root = ET.fromstring(res.svg)
    tags = {el.tag.split('}')[-1] for el in root.iter()}
    assert tags <= {'svg', 'defs', 'linearGradient', 'radialGradient', 'stop', 'g', 'rect', 'path'}
    assert not re.search(r'<image|<style|<script|href=', res.svg)
    assert res.outline_paths > 0
    assert res.gradients > 0                      # the shaded face became a gradient, not bands
    ids = re.findall(r'id="([^"]+)"', res.svg)
    assert all(i.startswith('test-') or i in ('fill', 'outline') for i in ids)


def test_flat_mode_has_no_gradients():
    res = vectorize(_sample(), Options(gradients=False))
    assert '<linearGradient' not in res.svg and '<radialGradient' not in res.svg


@pytest.mark.skipif(find_browser() is None, reason='needs Chrome/Edge for rendering')
def test_render_similarity():
    img = _sample()
    res = vectorize(img)
    out = render(res.svg, *img.size)
    sim, _ = similarity(img, out)
    assert sim > 97.0
