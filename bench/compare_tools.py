"""Other open-source tracers on the same 45 pictures, rendered and scored the same way as bench/readme.py.

    pip install vtracer==0.6.15 potracer==0.0.4     # benchmark only, not dependencies of this project
    python bench/readme.py                          # first: this project's results (bench/results/readme.json)
    python bench/compare_tools.py                   # -> bench/results/tools.json + tools.md

Tools and settings (each documented, none tuned per picture):
- VTracer (visioncortex, MIT) "default": the library's defaults (color, stacked, spline).
- VTracer "fine": its high-detail settings (color_precision 8, layer_difference 8, filter_speckle 2).
- Potrace (Selinger 2003; the pure-Python port `potracer`) traces black and white only. Colors are traced the way
  Inkscape's multi-color "Trace Bitmap" does: the picture is reduced to 8 colors (median cut), and every color is
  traced as the union of itself and the colors drawn after it, stacked largest first, so layers leave no gaps.
"""
from __future__ import annotations

import io
import json
import re
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'bench'))
from readme import RESULTS, SETS, score  # noqa: E402
from pngsvg.compare import render  # noqa: E402
from pngsvg.core import flatten  # noqa: E402


def vtracer_svg(img: Image.Image, fine: bool) -> str:
    import vtracer
    buf = io.BytesIO()
    flatten(img).save(buf, 'PNG')
    kw = {'color_precision': 8, 'layer_difference': 8, 'filter_speckle': 2} if fine else {}
    svg = vtracer.convert_raw_image_to_svg(buf.getvalue(), img_format='png', **kw)
    # its <svg> has width/height but no viewBox: add one so it scales like every other SVG here
    svg = svg[svg.index('<svg'):]
    return re.sub(r'<svg ([^>]*?)width="(\d+)" height="(\d+)"', r'<svg \1viewBox="0 0 \2 \3"', svg, count=1)


def potrace_path(mask: np.ndarray) -> str:
    import potrace
    out = []
    # potracer traces the False pixels of its bitmap (black = 0 in a grey picture): hand it the inverted mask.
    # Its curve optimisation can fail on a numerical edge case (math domain error); that layer is then traced
    # without it, as `potrace --longcurve` would.
    try:
        curves = potrace.Bitmap(~mask).trace(turdsize=2, alphamax=1.0, opticurve=True, opttolerance=0.2)
    except ValueError:
        curves = potrace.Bitmap(~mask).trace(turdsize=2, alphamax=1.0, opticurve=False)
    for curve in curves:
        x, y = curve.start_point.x, curve.start_point.y
        out.append(f'M{x:.2f} {y:.2f}')
        for s in curve.segments:
            if s.is_corner:
                out.append(f'L{s.c.x:.2f} {s.c.y:.2f}L{s.end_point.x:.2f} {s.end_point.y:.2f}')
            else:
                out.append(f'C{s.c1.x:.2f} {s.c1.y:.2f} {s.c2.x:.2f} {s.c2.y:.2f} {s.end_point.x:.2f} {s.end_point.y:.2f}')
        out.append('Z')
    return ''.join(out)


def potrace_svg(img: Image.Image, colors: int = 8) -> str:
    rgb = flatten(img)
    q = rgb.quantize(colors=colors, method=Image.Quantize.MEDIANCUT)
    idx = np.asarray(q)
    pal = np.array(q.getpalette()[:3 * colors]).reshape(-1, 3)
    used = [int(i) for i in np.argsort(-np.bincount(idx.ravel(), minlength=colors)) if (idx == i).any()]
    w, h = rgb.size
    body = [f'<rect width="{w}" height="{h}" fill="#{pal[used[0]][0]:02X}{pal[used[0]][1]:02X}{pal[used[0]][2]:02X}"/>']
    for n, i in enumerate(used[1:], 1):
        mask = np.isin(idx, used[n:])                           # this color and every color drawn after it
        d = potrace_path(mask)
        if d:
            c = pal[i]
            body.append(f'<path fill="#{c[0]:02X}{c[1]:02X}{c[2]:02X}" fill-rule="evenodd" d="{d}"/>')
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}">{"".join(body)}</svg>\n'


TOOLS = {'vtracer-default': lambda im: vtracer_svg(im, False), 'vtracer-fine': lambda im: vtracer_svg(im, True),
         'potrace-8': potrace_svg}


def main() -> int:
    ours = json.loads((RESULTS / 'readme.json').read_text(encoding='utf-8'))['sets']
    out_file = RESULTS / 'tools.json'
    data: dict = json.loads(out_file.read_text(encoding='utf-8')) if out_file.exists() else {}
    for set_name, root in SETS.items():
        for src in json.loads((root / 'sources.json').read_text(encoding='utf-8')):
            stem = Path(src['file']).stem
            key = f'{set_name}:{stem}'
            row = data.setdefault(key, {})
            o = ours[set_name][stem]
            row['ours'] = {k: o[k] for k in ('similarity', 'defects', 'psnr', 'ssim', 'bytes', 'paths', 'seconds')}
            img = Image.open(root / 'images' / src['file'])
            ref = flatten(img)
            for tool, make in TOOLS.items():
                if tool in row:
                    continue
                t = time.perf_counter()
                svg = make(img)
                secs = time.perf_counter() - t
                shot = render(svg, *img.size)
                renders = RESULTS / 'renders' / tool
                renders.mkdir(parents=True, exist_ok=True)
                shot.save(renders / f'{set_name}-{stem}.png')
                row[tool] = {**{k: v for k, v in score(ref, shot).items() if k in ('similarity', 'defects', 'psnr', 'ssim')},
                             'bytes': len(svg.encode()), 'paths': svg.count('<path'), 'seconds': round(secs, 2)}
                out_file.write_text(json.dumps(data, indent=1), encoding='utf-8')
            print(key, {t: (r['similarity'], r['defects'], r['bytes'] // 1024) for t, r in row.items()}, flush=True)
    out_file.write_text(json.dumps(data, indent=1), encoding='utf-8')
    return 0


if __name__ == '__main__':
    sys.exit(main())
