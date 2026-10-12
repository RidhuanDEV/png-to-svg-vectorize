"""Benchmark: vectorize a set of images and record quality, size, complexity and time.

    python bench/synthetic.py                                  # once: generate bench/images
    python bench/run.py                                         # bench/images -> bench/results/latest.json + table
    python bench/run.py --images D:/my/set --name private      # any folder (results stay local)
    python bench/run.py --baseline bench/baseline.json          # compare and flag regressions (exit 1)

Metrics per image: similarity (100 - MAE %, rendered with Chrome/Edge), % pixels within 24/255, SVG bytes,
Bezier/line segments, regions, gradients, seconds.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import time
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from pngsvg import Options, vectorize  # noqa: E402
from pngsvg.compare import render, similarity  # noqa: E402

_D = re.compile(r' d="([^"]+)"')
_TOK = re.compile(r'[MmLlCcQqZzHhVv]|-?(?:\d+\.?\d*|\.\d+)')
_ARITY = {'m': 2, 'l': 2, 'c': 6, 'q': 4, 'h': 1, 'v': 1}

SIM_DROP = 0.3       # regression if similarity drops more than this (points)
SIZE_GROWTH = 0.10   # regression if size grows more than 10 %


def count_segments(svg: str) -> int:
    n = 0
    for d in _D.findall(svg):
        cmd = None
        nums = 0
        for t in _TOK.findall(d):
            if t.isalpha():
                if cmd and cmd.lower() not in 'mz':
                    n += nums // _ARITY[cmd.lower()]
                cmd, nums = t, 0
            else:
                nums += 1
        if cmd and cmd.lower() not in 'mz':
            n += nums // _ARITY[cmd.lower()]
    return n


def run(images: list[Path]) -> dict:
    rows = {}
    for p in images:
        img = Image.open(p).convert('RGB')
        t = time.time()
        res = vectorize(img, Options(id_prefix=p.stem))
        secs = time.time() - t
        out = render(res.svg, *img.size)
        sim, within = similarity(img, out) if out is not None else (float('nan'), float('nan'))
        rows[p.stem] = {'similarity': round(sim, 3), 'within24': round(within, 2), 'bytes': len(res.svg.encode()),
                        'segments': count_segments(res.svg), 'regions': res.regions, 'gradients': res.gradients,
                        'seconds': round(secs, 2), 'size': list(img.size)}
        r = rows[p.stem]
        print(f"{p.stem:24s} sim {r['similarity']:6.2f}%  {r['bytes'] / 1024:7.0f} KB  {r['segments']:7d} seg  "
              f"{r['regions']:5d} reg  {r['seconds']:6.1f}s", flush=True)
    return rows


def table(rows: dict, base: dict | None = None) -> str:
    head = '| Image | Similarity | Within 24 | Size (bytes) | Segments | Regions | Time (s) |'
    lines = [head, '|---|---|---|---|---|---|---|']
    for k, r in rows.items():
        def delta(key, fmt, pct=False):
            v = r[key]
            if not base or k not in base:
                return fmt.format(v)
            b = base[k][key]
            d = (v - b) / b * 100 if pct and b else v - b
            return fmt.format(v) + (f' ({d:+.0f}%)' if pct else f' ({d:+.2f})')
        lines.append(f"| {k} | {delta('similarity', '{:.2f}%')} | {r['within24']:.1f}% | "
                     f"{delta('bytes', '{}', True)} | {delta('segments', '{}', True)} | {r['regions']} | "
                     f"{delta('seconds', '{:.1f}', True)} |")
    vals = list(rows.values())
    lines.append(f"| **median** | {statistics.median(v['similarity'] for v in vals):.2f}% | "
                 f"{statistics.median(v['within24'] for v in vals):.1f}% | "
                 f"{statistics.median(v['bytes'] for v in vals):.0f} | "
                 f"{statistics.median(v['segments'] for v in vals):.0f} | "
                 f"{statistics.median(v['regions'] for v in vals):.0f} | "
                 f"{statistics.median(v['seconds'] for v in vals):.1f} |")
    return '\n'.join(lines)


def regressions(rows: dict, base: dict) -> list[str]:
    out = []
    for k, r in rows.items():
        if k not in base:
            continue
        b = base[k]
        if r['similarity'] < b['similarity'] - SIM_DROP:
            out.append(f"{k}: similarity {b['similarity']:.2f} -> {r['similarity']:.2f}")
        if r['bytes'] > b['bytes'] * (1 + SIZE_GROWTH):
            out.append(f"{k}: size {b['bytes']} -> {r['bytes']}")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--images', type=Path, default=ROOT / 'bench' / 'images')
    ap.add_argument('--name', default='latest')
    ap.add_argument('--baseline', type=Path)
    a = ap.parse_args(argv)
    files = sorted(p for p in a.images.iterdir() if p.suffix.lower() in ('.png', '.webp', '.jpg', '.jpeg'))
    if not files:
        print(f'no images in {a.images} (run bench/synthetic.py first)')
        return 2
    rows = run(files)
    res_dir = ROOT / 'bench' / 'results'
    res_dir.mkdir(parents=True, exist_ok=True)
    (res_dir / f'{a.name}.json').write_text(json.dumps(rows, indent=1), encoding='utf-8')
    base = json.loads(a.baseline.read_text(encoding='utf-8')) if a.baseline else None
    md = table(rows, base)
    (res_dir / f'{a.name}.md').write_text(md + '\n', encoding='utf-8')
    print('\n' + md)
    if base:
        bad = regressions(rows, base)
        if bad:
            print('\nREGRESSIONS:\n  ' + '\n  '.join(bad))
            return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
