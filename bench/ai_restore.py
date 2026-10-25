"""Does the optional AI step help? A restoration benchmark.

Each clean image is degraded like a typical web picture (half size + JPEG quality 60). We vectorize the degraded
picture without AI and with each AI model, render the SVGs at the ORIGINAL size and compare with the CLEAN original:
an improvement means the AI recovered detail, not just that it copied the damage.

    python bench/ai_restore.py MODELS_DIR [--images bench/sets/images] [--limit 10] [--out bench/results/ai.md]
"""
from __future__ import annotations

import argparse
import io
import sys
import time
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from pngsvg import options_for, vectorize  # noqa: E402
from pngsvg.ai import enhance, providers_for  # noqa: E402
from pngsvg.compare import render, similarity  # noqa: E402


def degrade(img: Image.Image) -> Image.Image:
    small = img.resize((max(2, img.width // 2), max(2, img.height // 2)), Image.Resampling.BICUBIC)
    buf = io.BytesIO()
    small.save(buf, 'JPEG', quality=60)
    return Image.open(io.BytesIO(buf.getvalue())).convert('RGB')


def run_one(clean: Image.Image, src: Image.Image, preset: str) -> dict:
    t = time.perf_counter()
    res = vectorize(src, options_for(preset))
    secs = time.perf_counter() - t
    shot = render(res.svg, clean.width, clean.height)
    sim = similarity(clean, shot)[0] if shot else float('nan')
    return {'sim': sim, 'bytes': len(res.svg.encode()), 'regions': res.regions, 'secs': secs}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('models', type=Path)
    ap.add_argument('--images', type=Path, default=Path('bench/sets/images'))
    ap.add_argument('--limit', type=int, default=10)
    ap.add_argument('--target', type=int, default=2, help='AI output size relative to the degraded input')
    ap.add_argument('--accel', default='auto')
    ap.add_argument('--out', type=Path)
    a = ap.parse_args()

    print(f'providers: {providers_for(a.accel)}', flush=True)
    files = sorted(p for p in a.images.iterdir() if p.suffix.lower() in ('.png', '.webp', '.jpg', '.jpeg'))[:a.limit]
    rows, totals = [], {}
    for f in files:
        clean = Image.open(f).convert('RGB')
        if max(clean.size) > 1600:
            clean.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
        bad = degrade(clean)
        row = {'name': f.name, 'base': run_one(clean, bad, 'cartoon')}
        for model in ('general-x4', 'illustration-x4'):
            t = time.perf_counter()
            better = enhance(bad, a.models / f'{model}.onnx', a.accel, a.target)
            ai_secs = time.perf_counter() - t
            r = run_one(clean, better, 'cartoon')
            r['ai_secs'] = ai_secs
            row[model] = r
        rows.append(row)
        print(f"{f.name}: base {row['base']['sim']:.2f}  general {row['general-x4']['sim']:.2f}  "
              f"illustration {row['illustration-x4']['sim']:.2f}", flush=True)
        for k in ('base', 'general-x4', 'illustration-x4'):
            totals.setdefault(k, []).append(row[k])

    def med(xs):
        xs = sorted(xs)
        return xs[len(xs) // 2]

    lines = ['| image | no AI | AI general | AI illustration |', '|---|---|---|---|']
    for r in rows:
        lines.append(f"| {r['name']} | {r['base']['sim']:.2f}% · {r['base']['bytes'] // 1024} KB | "
                     f"{r['general-x4']['sim']:.2f}% · {r['general-x4']['bytes'] // 1024} KB | "
                     f"{r['illustration-x4']['sim']:.2f}% · {r['illustration-x4']['bytes'] // 1024} KB |")
    summary = []
    for k, label in (('base', 'no AI'), ('general-x4', 'AI general'), ('illustration-x4', 'AI illustration')):
        v = totals[k]
        extra = f", AI {med([x['ai_secs'] for x in v]):.1f} s" if k != 'base' else ''
        summary.append(f"- **{label}**: median similarity {med([x['sim'] for x in v]):.2f}%, "
                       f"median size {med([x['bytes'] for x in v]) // 1024} KB, "
                       f"median vectorize {med([x['secs'] for x in v]):.1f} s{extra}")
    report = '\n'.join(lines + [''] + summary) + '\n'
    print(report)
    if a.out:
        a.out.write_text(report, encoding='utf-8')


if __name__ == '__main__':
    main()
