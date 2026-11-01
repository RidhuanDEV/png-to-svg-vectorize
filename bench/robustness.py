"""Robustness: how much of the clean picture survives when the input is damaged the way real pictures are?

    python bench/robustness.py --models MODELS_DIR      # -> bench/results/robustness.json + robustness.md

Ten flat-art pictures from both sets are damaged three ways at three strengths: JPEG compression (quality 70, 50,
30), down-scaling (75 %, 50 %, 25 %, bicubic) and Gaussian noise (sigma 4, 8, 16 levels). Each damaged picture is
vectorized by this project (the style for its kind), by this project with the optional AI step ("Always": the
Real-ESRGAN illustration model, x4 then 2x) and by VTracer (default settings). Every SVG is rendered at the ORIGINAL
size and compared with the CLEAN original: a good score means the picture was recovered, not that its damage was
copied. Degradation models of this kind are how recent work tests vectorizers on real-world input (VectorArk, 2026).
"""
from __future__ import annotations

import argparse
import io
import json
import statistics
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'bench'))
from readme import PRESET, RESULTS, SETS, score, shown  # noqa: E402
from pngsvg import options_for, vectorize  # noqa: E402
from pngsvg.compare import render  # noqa: E402
from pngsvg.core import flatten  # noqa: E402

PICKS = [('E7', 'astronaut'), ('E7', 'cow'), ('E7', 'robot'), ('E7', 'shipment'), ('E7', 'icon-shop'),
         ('E7', 'flag-nepal'), ('E8', 'border-collie'), ('E8', 'pickle'), ('E8', 'tux-flat'), ('E8', 'ferris')]
DAMAGE = {'jpeg': (70, 50, 30), 'scale': (0.75, 0.5, 0.25), 'noise': (4, 8, 16)}


def damage(img: Image.Image, kind: str, level: float, seed: int) -> Image.Image:
    rgb = flatten(img)
    if kind == 'jpeg':
        buf = io.BytesIO()
        rgb.save(buf, 'JPEG', quality=int(level))
        return Image.open(io.BytesIO(buf.getvalue())).convert('RGB')
    if kind == 'scale':
        return rgb.resize((max(8, round(rgb.width * level)), max(8, round(rgb.height * level))), Image.Resampling.BICUBIC)
    noise = np.random.default_rng(seed).normal(0, level, (rgb.height, rgb.width, 3))
    return Image.fromarray(np.clip(np.asarray(rgb, np.float64) + noise, 0, 255).astype(np.uint8))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--models', type=Path)
    a = ap.parse_args(argv)
    from compare_tools import vtracer_svg
    model = a.models / 'illustration-x4.onnx' if a.models else None
    out_file = RESULTS / 'robustness.json'
    data: dict = json.loads(out_file.read_text(encoding='utf-8')) if out_file.exists() else {}
    cats = {}
    for set_name, root in SETS.items():
        for s in json.loads((root / 'sources.json').read_text(encoding='utf-8')):
            cats[(set_name, Path(s['file']).stem)] = (s['category'], root / 'images' / s['file'])
    for set_name, stem in PICKS:
        cat, path = cats[(set_name, stem)]
        clean_img = Image.open(path)
        clean = flatten(clean_img)
        preset, kw = PRESET[cat]
        if preset in ('logo', 'pixel'):            # a damaged copy has no transparency: keep its background
            kw = {'remove_bg': False}
        conditions = [('clean', 0)] + [(k, lv) for k, levels in DAMAGE.items() for lv in levels]
        for seed, (kind, level) in enumerate(conditions):
            key = f'{set_name}:{stem}|{kind}:{level}'
            if key in data:
                continue
            bad = clean if kind == 'clean' else damage(clean_img, kind, level, seed)
            row = {}
            res = vectorize(bad, options_for(preset, **kw))
            row['ours'] = score(clean, shown(res, bad.size).resize(clean.size, Image.Resampling.LANCZOS))
            if model and model.exists():
                from pngsvg.ai import enhance
                big = enhance(bad, model, 'auto', 2)
                opts = options_for(preset, **kw)
                opts.decimals = max(0, opts.decimals - 1)
                r2 = vectorize(big, opts)
                row['ours+AI'] = score(clean, shown(r2, big.size).resize(clean.size, Image.Resampling.LANCZOS))
            row['vtracer'] = score(clean, render(vtracer_svg(bad, False), *clean.size))
            data[key] = {m: {k: v for k, v in s.items() if k in ('similarity', 'defects', 'ssim')} for m, s in row.items()}
            out_file.write_text(json.dumps(data, indent=1), encoding='utf-8')
            print(key, {m: (s['similarity'], s['defects']) for m, s in data[key].items()}, flush=True)
    # summary: median over the pictures per condition and method
    methods = ['ours', 'ours+AI', 'vtracer']
    lines = ['| Damage | ' + ' | '.join(f'{m}: similarity · defects' for m in methods) + ' |',
             '|---|' + '---|' * len(methods)]
    conds = sorted({k.split('|')[1] for k in data}, key=lambda c: (['clean', 'jpeg', 'scale', 'noise'].index(c.split(':')[0]),
                                                                  -float(c.split(':')[1]) if c.startswith(('jpeg', 'scale')) else float(c.split(':')[1])))
    for c in conds:
        rows = [v for k, v in data.items() if k.endswith('|' + c)]
        cells = []
        for m in methods:
            vals = [r[m] for r in rows if m in r]
            cells.append(f"{statistics.median(v['similarity'] for v in vals):.2f} % · {statistics.median(v['defects'] for v in vals):.2f} %"
                         if vals else '—')
        lines.append(f'| {c} | ' + ' | '.join(cells) + ' |')
    md = '\n'.join(lines)
    (RESULTS / 'robustness.md').write_text(md + '\n', encoding='utf-8')
    print(md)
    return 0


if __name__ == '__main__':
    sys.exit(main())
