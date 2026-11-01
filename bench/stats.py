"""Paired statistics for the benchmark claims: is a difference real, how large, how certain?

    python bench/readme.py && python bench/versions.py --old old && python bench/compare_tools.py
    python bench/stats.py                     # -> bench/results/stats.json + stats.md

For every comparison (this version against 1.6.0, against VTracer and against Potrace) and every metric, on the same
pictures: the medians, the median of the per-picture differences with a bootstrap 95 % confidence interval (10 000
resamples, fixed seed), wins / ties / losses, the two-sided Wilcoxon signed-rank test (Wilcoxon 1945; Pratt's
treatment of zero differences), and the matched-pairs rank-biserial correlation as effect size (Kerby 2014: -1 to 1,
positive = this version better). Per-picture results are paired because the pictures differ far more from each
other than the methods do; an unpaired test would hide real differences.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / 'bench' / 'results'
METRICS = {'similarity': 1, 'defects': -1, 'ssim': 1, 'bytes': -1}     # +1: higher is better
TIE = {'similarity': 0.01, 'defects': 0.01, 'ssim': 0.0005, 'bytes': 0.0}  # |difference| below this: a tie


def paired(a: np.ndarray, b: np.ndarray, better: int, tie: float, seed: int = 0) -> dict:
    """b is this version, a the other one. Differences are taken so that positive = this version better."""
    d = (b - a) * better
    rng = np.random.default_rng(seed)
    boot = np.median(d[rng.integers(0, len(d), (10_000, len(d)))], axis=1)
    lo, hi = np.percentile(boot, [2.5, 97.5])
    nz = d[np.abs(d) > tie]
    if len(nz) >= 1 and np.any(nz != 0):
        w = stats.wilcoxon(d, zero_method='pratt')
        p = float(w.pvalue)
        ranks = stats.rankdata(np.abs(nz))
        r = float((ranks[nz > 0].sum() - ranks[nz < 0].sum()) / ranks.sum())
    else:
        p, r = 1.0, 0.0
    return {'n': int(len(d)), 'median_other': float(np.median(a)), 'median_this': float(np.median(b)),
            'median_gain': float(np.median(d)), 'ci95': [float(lo), float(hi)],
            'wins': int((d > tie).sum()), 'ties': int((np.abs(d) <= tie).sum()), 'losses': int((d < -tie).sum()),
            'p': p, 'r': r}


def comparisons() -> dict[str, list[tuple[str, dict, dict]]]:
    """name -> [(picture, other, this)]."""
    out: dict[str, list] = {}
    v = RESULTS / 'versions.json'
    if v.exists():
        out['this version vs 1.6.0'] = [(k, r['1.6.0'], r['now'] | {'category': r['category']})
                                        for k, r in json.loads(v.read_text(encoding='utf-8')).items()]
    t = RESULTS / 'tools.json'
    if t.exists():
        rows = json.loads(t.read_text(encoding='utf-8'))
        cats = {}
        readme = json.loads((RESULTS / 'readme.json').read_text(encoding='utf-8'))['sets']
        for s, rs in readme.items():
            for stem, r in rs.items():
                cats[f'{s}:{stem}'] = r['category']
        for tool in ('vtracer-default', 'vtracer-fine', 'potrace-8'):
            pairs = [(k, r[tool], r['ours'] | {'category': cats[k]}) for k, r in rows.items() if tool in r]
            if pairs:
                out[f'this version vs {tool}'] = pairs
    return out


def fmt(metric: str, x: float, sign: bool = False) -> str:
    plus = '+' if sign else ''
    if metric == 'bytes':
        return f'{x / 1024:{plus}.1f} KB'
    if metric == 'ssim':
        return f'{x:{plus}.4f}'
    return f'{x:{plus}.2f} %'


def main() -> int:
    result: dict = {}
    lines: list[str] = []
    for name, pairs in comparisons().items():
        result[name] = {}
        for group, keep in (('flat art', lambda c: c != 'poster'), ('all pictures', lambda c: True)):
            sel = [(k, o, t) for k, o, t in pairs if keep(t['category'])]
            if len(sel) < 6:
                continue
            result[name][group] = {}
            lines += [f'### {name} — {group} ({len(sel)} pictures)', '',
                      '| Metric | Other (median) | This (median) | Median gain [95 % CI] | Wins / ties / losses | Wilcoxon p | Effect r |',
                      '|---|---|---|---|---|---|---|']
            for m, better in METRICS.items():
                a = np.array([o[m] for _, o, _ in sel], float)
                b = np.array([t[m] for _, _, t in sel], float)
                s = paired(a, b, better, TIE[m])
                result[name][group][m] = s
                gain = fmt(m, s['median_gain'], True)
                ci = f"[{fmt(m, s['ci95'][0], True)}, {fmt(m, s['ci95'][1], True)}]"
                p = f"{s['p']:.1e}" if s['p'] < 0.001 else f"{s['p']:.3f}"
                lines.append(f"| {m} | {fmt(m, s['median_other'])} | {fmt(m, s['median_this'])} | {gain} {ci} | "
                             f"{s['wins']} / {s['ties']} / {s['losses']} | {p} | {s['r']:+.2f} |")
            lines.append('')
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / 'stats.json').write_text(json.dumps(result, indent=1), encoding='utf-8')
    md = 'Gain = per-picture difference, positive = this version better (lower defects / size count as better).\n\n' \
        + '\n'.join(lines)
    (RESULTS / 'stats.md').write_text(md + '\n', encoding='utf-8')
    print(md)
    return 0


if __name__ == '__main__':
    sys.exit(main())
