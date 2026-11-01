"""Before and after: the cases fixed since 1.6.0, vectorized by 1.6.0 and by this version, side by side.

    mkdir old && git archive v1.6.0 src | tar -x -C old        # the 1.6.0 engine, next to this one
    python bench/before_after.py --old old                     # -> bench/results/before_after.json
                                                               #    docs/images/evidence/before-after.webp

Both versions run in their own process with the same inputs (license-free: three E7 and three E8 images, one E7 image shrunk to
256 px, and two pictures generated here), and are scored with this version's metrics.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'bench'))
from evidence import BG, INK, MUTED, OUT, fit, font  # noqa: E402
from pngsvg.compare import defect_area, render, similarity  # noqa: E402
from pngsvg.core import flatten  # noqa: E402

RESULTS = ROOT / 'bench' / 'results'
E7 = ROOT / 'bench' / 'sets' / 'images'
E8 = ROOT / 'bench' / 'real' / 'images'

WORKER = '''
import json, sys
from PIL import Image
from pngsvg import options_for, vectorize
for job in json.loads(open(sys.argv[1], encoding='utf-8').read()):
    r = vectorize(Image.open(job['input']), options_for(job['preset'], **job['kw']))
    open(job['svg'], 'w', encoding='utf-8').write(r.svg)
    open(job['svg'] + '.json', 'w', encoding='utf-8').write(json.dumps({'crop': r.crop}))
'''


def night_scene() -> Image.Image:
    """An opaque dark painting-like picture (soft sky, texture, moon, hills): the kind 1.6.0 hollowed."""
    rng = np.random.default_rng(7)
    h, w = 540, 960
    y, x = np.mgrid[0:h, 0:w]
    sky = np.stack([10 + 30 * y / h, 18 + 40 * y / h, 45 + 60 * y / h], -1) + rng.normal(0, 3, (h, w, 1))
    moon = np.hypot(x - 700, y - 150) < 70
    sky[moon] = [225, 230, 240]
    glow = np.clip(1 - np.hypot(x - 700, y - 150) / 220, 0, 1)[..., None] * 40
    sky = sky + glow * ~moon[..., None]
    hills = y > 380 + 40 * np.sin(x / 90) + 20 * np.sin(x / 37)
    sky[hills] = np.array([12, 16, 28]) + rng.normal(0, 2, (int(hills.sum()), 1))
    figure = (np.abs(x - 300) < 14) & (y > 300) & (y < 420) | (np.hypot(x - 300, y - 285) < 16)
    sky[figure] = [8, 10, 16]
    return Image.fromarray(np.clip(sky, 0, 255).astype(np.uint8))


def thin_bars() -> Image.Image:
    img = Image.new('RGB', (480, 300), 'white')
    d = ImageDraw.Draw(img)
    for i, width in enumerate((4, 6, 8, 12)):
        d.rectangle((60 + i * 100, 40, 60 + i * 100 + width - 1, 260), fill=(30, 41, 59))
    d.rectangle((40, 270, 440, 277), fill=(234, 88, 12))
    return img


def cases(tmp: Path) -> list[dict]:
    small = Image.open(E7 / 'cow.png').convert('RGBA')
    small = small.resize((round(small.width * 256 / max(small.size)), 256 * small.height // max(small.size)),
                         Image.Resampling.LANCZOS)
    made = {'night.png': night_scene(), 'thin-bars.png': thin_bars(), 'cow-256.png': small}
    for name, im in made.items():
        im.save(tmp / name)
    return [
        {'id': 'icon-shop', 'title': 'Flat icon, Logo style: a color and its darker shade', 'input': str(E7 / 'icon-shop.png'),
         'preset': 'logo', 'kw': {}},
        {'id': 'flag-brazil', 'title': 'Flag, Logo style (background kept): a color on 0.7 % of the picture',
         'input': str(E7 / 'flag-brazil.png'), 'preset': 'logo', 'kw': {'remove_bg': False}},
        {'id': 'tux-flat', 'title': 'Flat icon, Logo style: a grey between black and white',
         'input': str(E8 / 'tux-flat.png'), 'preset': 'logo', 'kw': {}},
        {'id': 'bird-pixel-art', 'title': 'Pixel art (background kept): checkerboard and 1-pixel details',
         'input': str(E8 / 'bird-pixel-art.png'), 'preset': 'pixel', 'kw': {'remove_bg': False}},
        {'id': 'evil-twin', 'title': 'Line drawing, Logo style: a 3 px ring (1.6 cut it at every thin spot)',
         'input': str(E8 / 'evil-twin.png'), 'preset': 'logo', 'kw': {'remove_bg': False}},
        {'id': 'futuristic-mascot', 'title': 'Cartoon style: a grey reflection on a black screen (1.6: ink)',
         'input': str(E7 / 'futuristic-mascot.png'), 'preset': 'cartoon', 'kw': {}},
        {'id': 'night', 'title': 'Opaque dark picture, Logo style', 'input': str(tmp / 'night.png'), 'preset': 'logo',
         'kw': {}},
        {'id': 'thin-bars', 'title': 'Thin bars (4-12 px), Logo style', 'input': str(tmp / 'thin-bars.png'),
         'preset': 'logo', 'kw': {}},
        {'id': 'cow-256', 'title': 'Small picture (256 px), Cartoon style', 'input': str(tmp / 'cow-256.png'),
         'preset': 'cartoon', 'kw': {}},
    ]


def run(src_dir: Path, jobs: list[dict], tag: str, tmp: Path) -> None:
    spec = [{'input': j['input'], 'preset': j['preset'], 'kw': j['kw'], 'svg': str(tmp / f"{j['id']}.{tag}.svg")}
            for j in jobs]
    (tmp / f'{tag}.json').write_text(json.dumps(spec), encoding='utf-8')
    env = {**os.environ, 'PYTHONPATH': str(src_dir)}
    subprocess.run([sys.executable, '-c', WORKER, str(tmp / f'{tag}.json')], env=env, check=True, cwd=tmp)


CHECKER = 'repeating-conic-gradient(#d4d4d8 0 25%, #fff 0 50%) 0 0/16px 16px'


def checker(size: tuple[int, int]) -> Image.Image:
    y, x = np.mgrid[0:size[1], 0:size[0]]
    light = ((x // 8 + y // 8) % 2).astype(bool)
    return Image.fromarray(np.where(light[..., None], 255, np.array([212, 212, 216])).astype(np.uint8))


def shown(svg: str, crop: list[float] | None, size: tuple[int, int], background: str = '#fff') -> Image.Image:
    """The SVG placed on the picture; on white for the scores, on a checkerboard to show transparent holes."""
    if crop is None:
        return render(svg, *size, background)
    x, y, w, h = crop
    part = render(svg, max(1, round(w)), max(1, round(h)), background)
    canvas = Image.new('RGB', size, (255, 255, 255)) if background == '#fff' else checker(size)
    canvas.paste(part, (round(x), round(y)))
    return canvas


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--old', type=Path, required=True, help='folder holding the old version\'s src/ (git archive)')
    a = ap.parse_args(argv)
    rows = []
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        jobs = cases(tmp)
        run(a.old.resolve() / 'src', jobs, 'old', tmp)
        run(ROOT / 'src', jobs, 'new', tmp)
        cell, pad, head, foot = 300, 14, 30, 30
        blocks = []                                   # (title, [picture, 1.6.0, now], [caption 1.6.0, caption now])
        for job in jobs:
            src = Image.open(job['input'])
            ref = flatten(src)
            row = {'id': job['id'], 'title': job['title']}
            pics, notes = [fit(ref, cell, cell, Image.Resampling.LANCZOS)], []
            for tag in ('old', 'new'):
                svg = (tmp / f"{job['id']}.{tag}.svg").read_text(encoding='utf-8')
                crop = json.loads((tmp / f"{job['id']}.{tag}.svg.json").read_text(encoding='utf-8'))['crop']
                out = shown(svg, crop, src.size)
                row[tag] = {'similarity': round(similarity(ref, out)[0], 3), 'defects': round(defect_area(ref, out), 3),
                            'bytes': len(svg.encode()), 'paths': svg.count('<path')}
                pics.append(fit(shown(svg, crop, src.size, CHECKER), cell, cell, Image.Resampling.LANCZOS))
                notes.append(f"{row[tag]['similarity']:.2f} % · defects {row[tag]['defects']:.2f} % · "
                             f"{row[tag]['bytes'] / 1024:.1f} KB")
            blocks.append((job['title'], pics, notes))
            rows.append(row)
            print(row, flush=True)
        height = 64 + sum(head + max(p.height for p in pics) + foot for _, pics, _ in blocks)
        canvas = Image.new('RGB', (3 * cell + 4 * pad, height), BG)
        d = ImageDraw.Draw(canvas)
        for c, label in enumerate(('source', '1.6.0', 'now')):
            d.text((pad + c * (cell + pad), 10), label, fill=INK, font=font(20))
        d.text((pad, 36), 'checkerboard = transparent (a hole in the SVG)', fill=MUTED, font=font(13))
        top = 64
        for title, pics, notes in blocks:
            d.text((pad, top), title, fill=INK, font=font(16))
            tall = max(p.height for p in pics)
            for c, pic in enumerate(pics):
                canvas.paste(pic, (pad + c * (cell + pad), top + head))
            for c, note in enumerate(notes, 1):
                d.text((pad + c * (cell + pad), top + head + tall + 4), note, fill=MUTED, font=font(13))
            top += head + tall + foot
        OUT.mkdir(parents=True, exist_ok=True)
        canvas.save(OUT / 'before-after.webp', quality=85, method=6)
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / 'before_after.json').write_text(json.dumps(rows, indent=1), encoding='utf-8')
    return 0


if __name__ == '__main__':
    sys.exit(main())
