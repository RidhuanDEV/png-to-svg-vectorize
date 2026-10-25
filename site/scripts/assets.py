"""Build the website's images: the gallery from the license-free comparison set (bench/sets, CC0 / public domain) and
responsive WebP copies of the app screenshots (docs/images).

    python bench/fetch_sets.py && python site/scripts/assets.py

For each picked image: WebP previews of the original (public/gallery/<name>-<width>.webp), the SVG made by the engine
with the given style (public/gallery/<name>.svg), and the measured numbers (src/generated/gallery.json): similarity of
the SVG render to the original, file sizes, time. Screenshots become public/shots/<name>-<width>.webp. Re-run after
engine changes or new screenshots; the output is committed.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))

from pngsvg import options_for, vectorize  # noqa: E402
from pngsvg.compare import render, similarity  # noqa: E402
from pngsvg.core import flatten  # noqa: E402

PICKS = [  # file, style
    ('caticorn.png', 'cartoon'),
    ('fish-mascot.png', 'cartoon'),
    ('robot.png', 'cartoon'),
    ('mountain-landscape.png', 'flat'),
    ('flag-brazil.png', 'logo'),
    ('icon-shop.png', 'logo'),
    ('kazoo.png', 'cartoon'),
    ('great-wave.jpg', 'poster'),
]
HERO = 'caticorn.png'          # also exported at full size: the home page zooms into it
WIDTHS = (480, 720, 960)       # gallery preview widths (srcset)
SHOT_WIDTHS = (680, 1360)      # screenshot widths (srcset)
OUT = ROOT / 'site' / 'public' / 'gallery'
SHOTS = ROOT / 'site' / 'public' / 'shots'
DATA = ROOT / 'site' / 'src' / 'generated' / 'gallery.json'


def webp(img: Image.Image, width: int, path: Path, quality: int) -> Image.Image:
    copy = img.copy()
    copy.thumbnail((width, width * 4), Image.Resampling.LANCZOS)
    copy.save(path, 'WEBP', quality=quality, method=6)
    return copy


def main() -> int:
    sources = {r['file']: r for r in json.loads((ROOT / 'bench/sets/sources.json').read_text(encoding='utf-8'))}
    for d in (OUT, SHOTS, DATA.parent):
        d.mkdir(parents=True, exist_ok=True)
    items = []
    for file, style in PICKS:
        src_path = ROOT / 'bench/sets/images' / file
        src = Image.open(src_path)
        stem = src_path.stem
        t = time.perf_counter()
        res = vectorize(src, options_for(style, id_prefix=stem))
        seconds = time.perf_counter() - t
        ref = flatten(src)
        shown = render(res.svg, *src.size)
        sim = similarity(ref, shown)[0] if shown is not None else None
        (OUT / f'{stem}.svg').write_text(res.svg, encoding='utf-8')
        if file == HERO:
            ref.save(OUT / f'{stem}-full.webp', 'WEBP', quality=90, method=6)
        previews = [webp(ref, w, OUT / f'{stem}-{w}.webp', 84) for w in WIDTHS]
        meta = sources[file]
        items.append({
            'name': stem, 'file': file, 'category': meta['category'], 'style': style,
            'title': meta['title'].removeprefix('File:').rsplit('.', 1)[0].replace('_', ' '),
            'artist': meta['artist'] or '', 'license': meta['license'], 'page': meta['page'],
            'width': src.width, 'height': src.height,
            'previewWidth': previews[-1].width, 'previewHeight': previews[-1].height,
            'similarity': round(sim, 2) if sim is not None else None, 'svgBytes': len(res.svg.encode()),
            'sourceBytes': src_path.stat().st_size, 'seconds': round(seconds, 1), 'regions': res.regions,
            'gradients': res.gradients,
        })
        print(f'{file:24s} {style:8s} {sim:.2f}% {len(res.svg) // 1024} KB {seconds:.1f}s', flush=True)
    DATA.write_text(json.dumps(items, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    for png in sorted((ROOT / 'docs' / 'images').glob('*.png')):
        img = Image.open(png).convert('RGB')
        for w in SHOT_WIDTHS:
            webp(img, w, SHOTS / f'{png.stem}-{w}.webp', 86)
    return 0


if __name__ == '__main__':
    sys.exit(main())
