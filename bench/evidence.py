"""Pictures of the benchmark results for the README: what the numbers look like.

    python bench/readme.py        # first: renders in bench/results/renders
    python bench/evidence.py      # -> docs/images/evidence/*.webp

For each picked image: the source, the SVG as rendered by Chrome, and where they visibly differ (red: CIEDE2000 > 5
after removing anti-aliasing lines, see pngsvg.compare.defect_map), then the same three at the place with the most
error, enlarged. Plus one overview per set with every image (source above, SVG below).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from pngsvg.compare import defect_map  # noqa: E402

RESULTS = ROOT / 'bench' / 'results'
OUT = ROOT / 'docs' / 'images' / 'evidence'
PICKS = {'E7': ['cow', 'shipment', 'icon-shop', 'flag-brazil', 'starry-night'],
         'E8': ['border-collie', 'gray-cat', 'tux-flat', 'bird-pixel-art', 'spot-cow']}
INK, MUTED, BG, RED = (17, 24, 39), (107, 114, 128), (255, 255, 255), (220, 38, 38)


def font(size: int) -> ImageFont.ImageFont:
    return ImageFont.load_default(size=size)


def defects_view(src: Image.Image, defects: np.ndarray) -> Image.Image:
    """The source faded to light grey with the visible defects in red."""
    grey = np.asarray(src.convert('L'), np.float64)[..., None] * 0.25 + 191
    view = np.repeat(grey, 3, axis=2)
    view[defects] = RED
    return Image.fromarray(view.astype(np.uint8))


def worst_box(src: Image.Image, out: Image.Image, side: int) -> tuple[int, int, int, int]:
    """The side x side window with the most absolute error."""
    err = np.abs(np.asarray(src, np.float64) - np.asarray(out, np.float64)).sum(-1)
    local = ndimage.uniform_filter(err, side, mode='constant')
    y, x = np.unravel_index(int(np.argmax(local)), local.shape)
    x0 = int(np.clip(x - side // 2, 0, src.width - side))
    y0 = int(np.clip(y - side // 2, 0, src.height - side))
    return x0, y0, x0 + side, y0 + side


def fit(im: Image.Image, w: int, h: int, resample: Image.Resampling) -> Image.Image:
    im = im.copy()
    scale = min(w / im.width, h / im.height)
    return im.resize((max(1, round(im.width * scale)), max(1, round(im.height * scale))), resample)


def panel(stem: str, row: dict, renders: Path) -> Image.Image:
    src = Image.open(renders / f'{stem}.source.png').convert('RGB')
    out = Image.open(renders / f'{stem}.svg.png').convert('RGB')
    defects = defect_map(src, out)
    view = defects_view(src, defects)
    cell, pad, head = 380, 16, 64
    side = max(32, min(src.size) // 6)
    box = worst_box(src, out, side)
    canvas = Image.new('RGB', (3 * cell + 4 * pad, head + 2 * cell + 3 * pad + 28), BG)
    d = ImageDraw.Draw(canvas)
    style = {'cartoon': 'Cartoon', 'flat': 'Flat illustration', 'poster': 'Poster', 'logo': 'Logo',
             'pixel': 'Pixel art'}[row['preset']]
    d.text((pad, 12), f'{stem}  ·  {row["format"]} {row["size"][0]}×{row["size"][1]}  ·  {style} style', fill=INK,
           font=font(22))
    d.text((pad, 40), f'similarity {row["similarity"]:.2f} %   ·   visible-defect area {row["defects"]:.2f} %   ·   '
                      f'SSIM {row["ssim"]:.3f}   ·   {row["bytes"] / 1024:.1f} KB, {row["paths"]} paths', fill=MUTED,
           font=font(16))
    labels = ['source', 'SVG (rendered by Chrome)', 'visible defects (red)']
    for i, (im, label) in enumerate(zip((src, out, view), labels)):
        x = pad + i * (cell + pad)
        big = fit(im, cell, cell, Image.Resampling.LANCZOS)
        canvas.paste(big, (x + (cell - big.width) // 2, head + (cell - big.height) // 2))
        sx, sy = big.width / im.width, big.height / im.height
        ox, oy = x + (cell - big.width) // 2, head + (cell - big.height) // 2
        d.rectangle((ox + box[0] * sx, oy + box[1] * sy, ox + box[2] * sx, oy + box[3] * sy), outline=(37, 99, 235),
                    width=2)
        d.text((x, head + cell + 4), label, fill=MUTED, font=font(14))
        crop = fit(im.crop(box), cell, cell, Image.Resampling.NEAREST)
        canvas.paste(crop, (x, head + cell + pad + 28))
    d.text((pad, canvas.height - 22), f'blue box: the {side}×{side} px area with the most error, enlarged below',
           fill=MUTED, font=font(14))
    return canvas


def overview(name: str, rows: dict, renders: Path, cell: int = 150) -> Image.Image:
    cols = 9
    n = len(rows)
    lines = (n + cols - 1) // cols
    canvas = Image.new('RGB', (cols * cell, lines * (2 * cell + 34)), BG)
    d = ImageDraw.Draw(canvas)
    for i, (stem, row) in enumerate(rows.items()):
        x, y = (i % cols) * cell, (i // cols) * (2 * cell + 34)
        for j, part in enumerate(('source', 'svg')):
            im = fit(Image.open(renders / f'{stem}.{part}.png').convert('RGB'), cell - 8, cell - 8,
                     Image.Resampling.LANCZOS)
            canvas.paste(im, (x + (cell - im.width) // 2, y + j * cell + (cell - im.height) // 2))
        d.text((x + 4, y + 2 * cell), stem[:20], fill=INK, font=font(13))
        d.text((x + 4, y + 2 * cell + 16), f'{row["similarity"]:.2f}% · defects {row["defects"]:.2f}%', fill=MUTED,
               font=font(11))
    return canvas


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.parse_args(argv)
    data = json.loads((RESULTS / 'readme.json').read_text(encoding='utf-8'))
    OUT.mkdir(parents=True, exist_ok=True)
    for name, rows in data['sets'].items():
        renders = RESULTS / 'renders' / name
        overview(name, rows, renders).save(OUT / f'overview-{name.lower()}.webp', quality=82, method=6)
        for stem in PICKS[name]:
            panel(stem, rows[stem], renders).save(OUT / f'{stem}.webp', quality=85, method=6)
            print('wrote', OUT / f'{stem}.webp')
    return 0


if __name__ == '__main__':
    sys.exit(main())
