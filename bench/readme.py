"""The benchmark shown in the README: every image of both license-free sets, the style a user would pick.

    python bench/fetch_sets.py && python bench/fetch_sets.py --set real   # once: CC0 / public-domain pictures
    python bench/readme.py                           # -> bench/results/readme.json + readme.md + renders/
    python bench/readme.py --models MODELS_DIR       # + the small-picture study with the AI column
    python bench/evidence.py                         # pictures of the results for the README (docs/images/evidence)
    NVIDIA_API_KEY=... python bench/judge.py         # optional: a vision model lists visible defects

Sets: E7 (bench/sets) are renders of CC0 vector art, the cleanest possible input; E8 (bench/real) are pictures that
were made as rasters: PNGs from 300 px, JPEG clipart, pixel art, a 3D render. Every image is used (no selection).
The style follows the category in sources.json: cartoon -> Cartoon, flat -> Flat illustration, poster (photos,
paintings, renders) -> Poster, icon -> Logo, logo (flags) -> Logo with the background kept (a flag has no
background), pixel -> Pixel art. Logo and Pixel art keep an opaque picture's background (leaving it out is a
choice, not an error; a transparent picture's background is left out as usual). Pictures not in the Cartoon style
are also run with Cartoon, the one style for everything. The SVG is rendered with headless Chrome/Edge at the picture's size (a trimmed logo is put back where it
sits) and compared with the source flattened on white.

Metrics: similarity = 100 - mean absolute RGB error % (the app's score); defect area = share of the picture with a
visible difference (CIEDE2000 > 5, edge lines of anti-aliasing removed), the number that catches a lost color or a
missing shape; PSNR; SSIM (luma, Wang et al. 2004); similarity away from color edges; SVG bytes, paths, seconds
(single process).

The small-picture study shrinks 10 E7 images to 256 px on the long side (Lanczos) and vectorizes them three ways:
the 1x grid (prescale=1, as before 1.7), the default 2x grid for pictures under 512 px, and the optional AI step
(Real-ESRGAN illustration model, x4 then 2x, as the app's Automatic mode does). Scores are against the 256 px picture.
"""
from __future__ import annotations

import argparse
import json
import platform
import statistics
import sys
import time
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from pngsvg import __version__, options_for, vectorize  # noqa: E402
from pngsvg.compare import defect_area, edge_split, psnr, render, similarity, ssim  # noqa: E402
from pngsvg.core import Options, Result, flatten  # noqa: E402

SETS = {'E7': ROOT / 'bench' / 'sets', 'E8': ROOT / 'bench' / 'real'}
RESULTS = ROOT / 'bench' / 'results'
PRESET = {'cartoon': ('cartoon', {}), 'cartoon-raster': ('cartoon', {}), 'flat': ('flat', {}),
          'poster': ('poster', {}), 'icon': ('logo', {}), 'logo': ('logo', {'remove_bg': False}),
          'pixel': ('pixel', {})}
LABEL = {'cartoon': 'Cartoon', 'flat': 'Flat illustration', 'poster': 'Poster', 'logo': 'Logo', 'pixel': 'Pixel art'}
SMALL = ['astronaut', 'cow', 'penguin', 'fish-mascot', 'shipment', 'flag-nepal', 'flag-south-africa',
         'icon-shop', 'icon-flask', 'icon-cat']


def shown(res: Result, size: tuple[int, int]) -> Image.Image:
    """The SVG as it looks on the picture: a trimmed logo is put back at its place on white."""
    if res.crop is None:
        return render(res.svg, *size)
    x, y, w, h = res.crop
    part = render(res.svg, max(1, round(w)), max(1, round(h))).convert('RGBA')
    canvas = Image.new('RGBA', size, (255, 255, 255, 255))
    canvas.alpha_composite(part, (round(x), round(y)))
    return canvas.convert('RGB')


def transparent(img: Image.Image) -> bool:
    return img.convert('RGBA').getchannel('A').getextrema()[0] < 255


def score(ref: Image.Image, out: Image.Image) -> dict:
    flat, on_edges = edge_split(ref, out)
    return {'similarity': round(similarity(ref, out)[0], 3), 'defects': round(defect_area(ref, out), 3),
            'psnr': round(psnr(ref, out), 2), 'ssim': round(ssim(ref, out), 4), 'flat': round(flat, 3),
            'edge_error': round(on_edges, 1)}


def run_set(name: str) -> dict:
    root = SETS[name]
    renders = RESULTS / 'renders' / name
    renders.mkdir(parents=True, exist_ok=True)
    rows = {}
    for src in json.loads((root / 'sources.json').read_text(encoding='utf-8')):
        path = root / 'images' / src['file']
        if not path.exists():
            raise SystemExit(f'missing {path}: run python bench/fetch_sets.py' + ('' if name == 'E7' else ' --set real'))
        img = Image.open(path)
        preset, kw = PRESET[src['category']]
        if preset in ('logo', 'pixel') and not transparent(img):
            kw = {'remove_bg': False}          # removing an opaque background is a choice, not an error to score
        t = time.perf_counter()
        res = vectorize(img, options_for(preset, **kw))
        secs = time.perf_counter() - t
        ref = flatten(img)
        out = shown(res, img.size)
        ref.save(renders / f'{path.stem}.source.png')
        out.save(renders / f'{path.stem}.svg.png')
        (renders / f'{path.stem}.svg').write_text(res.svg, encoding='utf-8')
        row = {'category': src['category'], 'preset': preset, 'background_kept': bool(kw), 'size': list(img.size),
               'format': path.suffix.lstrip('.').upper(), **score(ref, out),
               'bytes': len(res.svg.encode()), 'paths': res.svg.count('<path'), 'seconds': round(secs, 2)}
        if preset != 'cartoon':              # the same picture with the one-style-for-everything default
            alt = vectorize(img, options_for('cartoon'))
            alt_score = score(ref, shown(alt, img.size))
            row['cartoon'] = {'similarity': alt_score['similarity'], 'defects': alt_score['defects'],
                              'bytes': len(alt.svg.encode())}
        rows[path.stem] = row
        print(f"{name} {path.stem:20s} {preset:8s} {row['similarity']:7.3f}%  defects {row['defects']:6.3f}%  "
              f"{row['psnr']:5.1f} dB  SSIM {row['ssim']:.4f}  {row['bytes'] / 1024:6.0f} KB  {row['paths']:5d} paths  "
              f"{secs:5.1f}s", flush=True)
    return rows


def small_set(models: Path | None) -> dict:
    from pngsvg.ai import enhance
    root = SETS['E7']
    rows = {}
    cats = {Path(s['file']).stem: (s['category'], s['file'])
            for s in json.loads((root / 'sources.json').read_text(encoding='utf-8'))}
    model = models / 'illustration-x4.onnx' if models else None
    for stem in SMALL:
        cat, file = cats[stem]
        img = Image.open(root / 'images' / file)
        f = 256 / max(img.size)
        small = img.convert('RGBA').resize((round(img.width * f), round(img.height * f)), Image.Resampling.LANCZOS)
        ref = flatten(small)
        preset, kw = PRESET[cat]
        row: dict = {'preset': preset}
        for name, prescale in (('grid1', 1), ('grid2', None)):
            opts: Options = options_for(preset, **kw)
            opts.prescale = prescale
            t = time.perf_counter()
            res = vectorize(small, opts)
            row[name] = {**score(ref, shown(res, small.size)), 'bytes': len(res.svg.encode()),
                         'seconds': round(time.perf_counter() - t, 2)}
        if model and model.exists():
            t = time.perf_counter()
            big = enhance(small, model, 'auto', 2)
            opts = options_for(preset, **kw)
            opts.decimals = max(0, opts.decimals - 1)
            res = vectorize(big, opts)
            out = shown(res, big.size).resize(small.size, Image.Resampling.LANCZOS)
            row['ai'] = {**score(ref, out), 'bytes': len(res.svg.encode()), 'seconds': round(time.perf_counter() - t, 2)}
        rows[stem] = row
        print('small', stem, {k: (v['similarity'], v['bytes']) for k, v in row.items() if isinstance(v, dict)}, flush=True)
    return rows


def _kb(n: float) -> str:
    return f'{n / 1024:.1f} KB' if n < 10 * 1024 else f'{n / 1024:.0f} KB'


def md_set(rows: dict) -> str:
    out = ['| Image | Kind | Style | Similarity | Defect area | PSNR | SSIM | Size | Paths | Time | Cartoon style |',
           '|---|---|---|---|---|---|---|---|---|---|---|']
    for k, r in rows.items():
        preset = LABEL[r['preset']] + (' (background kept)' if r['background_kept'] else '')
        alt = (f"{r['cartoon']['similarity']:.2f}% · {r['cartoon']['defects']:.2f}% · {_kb(r['cartoon']['bytes'])}"
               if 'cartoon' in r else 'same')
        out.append(f"| {k} ({r['format']}, {r['size'][0]}×{r['size'][1]}) | {r['category']} | {preset} | "
                   f"{r['similarity']:.2f}% | {r['defects']:.2f}% | {r['psnr']:.1f} dB | {r['ssim']:.3f} | "
                   f"{_kb(r['bytes'])} | {r['paths']} | {r['seconds']:.1f} s | {alt} |")
    return '\n'.join(out)


def md_groups(sets: dict) -> str:
    out = ['| Set | Group | Images | Median similarity | Median defect area | Worst defect area | Median SSIM | '
           'Median size |', '|---|---|---|---|---|---|---|---|']
    for name, rows in sets.items():
        groups = {'flat art (icons, flags, flat, cartoon, pixel)': [r for r in rows.values() if r['category'] != 'poster'],
                  'photos, paintings, 3D renders': [r for r in rows.values() if r['category'] == 'poster']}
        for g, items in groups.items():
            if items:
                out.append(f"| {name} | {g} | {len(items)} | {statistics.median(r['similarity'] for r in items):.2f}% | "
                           f"{statistics.median(r['defects'] for r in items):.2f}% | "
                           f"{max(r['defects'] for r in items):.2f}% | {statistics.median(r['ssim'] for r in items):.3f} | "
                           f"{_kb(statistics.median(r['bytes'] for r in items))} |")
    return '\n'.join(out)


def md_small(rows: dict) -> str:
    ai = any('ai' in r for r in rows.values())
    head = '| Image (256 px) | Style | 1× grid (before 1.7) | 2× grid (default) |' + (' AI + 2× |' if ai else '')
    out = [head, '|---|---|---|---|' + ('---|' if ai else '')]
    for k, r in rows.items():
        cells = [f"{r[n]['similarity']:.2f}% · {r[n]['defects']:.2f}% · {_kb(r[n]['bytes'])}"
                 for n in ('grid1', 'grid2', 'ai') if n in r]
        out.append(f"| {k} | {LABEL[r['preset']]} | " + ' | '.join(cells) + ' |')
    for preset_kind, keep in (('Cartoon / Flat', lambda r: r['preset'] != 'logo'), ('Logo', lambda r: r['preset'] == 'logo')):
        part = [r for r in rows.values() if keep(r)]
        med = [f"{statistics.median(r[n]['similarity'] for r in part):.2f}% · "
               f"{statistics.median(r[n]['defects'] for r in part):.2f}%"
               for n in ('grid1', 'grid2', 'ai') if all(n in r for r in part)]
        out.append(f'| **median, {preset_kind}** | | ' + ' | '.join(f'**{m}**' for m in med) + ' |')
    return '\n'.join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--models', type=Path, help='folder with illustration-x4.onnx: adds the AI column')
    ap.add_argument('--only', choices=['E7', 'E8', 'small'], help='run one part, keep the others from readme.json')
    a = ap.parse_args(argv)
    old = RESULTS / 'readme.json'
    data = json.loads(old.read_text(encoding='utf-8')) if a.only and old.exists() else {}
    data['machine'] = f'{platform.processor() or platform.machine()}, {platform.system()} {platform.release()}'
    data['version'] = __version__
    data.setdefault('sets', {})
    for name in SETS:
        if a.only in (None, name):
            data['sets'][name] = run_set(name)
    if a.only in (None, 'small'):
        data['small'] = small_set(a.models)
    RESULTS.mkdir(parents=True, exist_ok=True)
    old.write_text(json.dumps(data, indent=1), encoding='utf-8')
    parts = [md_groups(data['sets'])]
    parts += [f'### {name}\n\n' + md_set(rows) for name, rows in data['sets'].items()]
    if 'small' in data:
        parts.append('### Small pictures\n\n' + md_small(data['small']))
    md = '\n\n'.join(parts) + '\n'
    (RESULTS / 'readme.md').write_text(md, encoding='utf-8')
    print('\n' + md)
    return 0


if __name__ == '__main__':
    sys.exit(main())
