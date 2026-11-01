"""1.6.0 and this version on every picture of both sets, for paired statistics (bench/stats.py).

    mkdir old && git archive v1.6.0 src | tar -x -C old
    python bench/readme.py                       # this version (bench/results/readme.json)
    python bench/versions.py --old old           # -> bench/results/versions.json

The old version runs in its own process with the same inputs and the same style per picture as bench/readme.py.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'bench'))
from before_after import run, shown  # noqa: E402
from readme import PRESET, RESULTS, SETS, score, transparent  # noqa: E402
from pngsvg.core import flatten  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--old', type=Path, required=True)
    a = ap.parse_args(argv)
    now = json.loads((RESULTS / 'readme.json').read_text(encoding='utf-8'))['sets']
    jobs, meta = [], {}
    for set_name, root in SETS.items():
        for src in json.loads((root / 'sources.json').read_text(encoding='utf-8')):
            path = root / 'images' / src['file']
            preset, kw = PRESET[src['category']]
            if preset in ('logo', 'pixel') and not transparent(Image.open(path)):
                kw = {'remove_bg': False}
            jid = f'{set_name}-{path.stem}'
            jobs.append({'id': jid, 'input': str(path), 'preset': preset, 'kw': kw})
            meta[jid] = (set_name, path.stem, path)
    out = {}
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        run(a.old.resolve() / 'src', jobs, 'old', tmp)
        for job in jobs:
            set_name, stem, path = meta[job['id']]
            img = Image.open(path)
            svg = (tmp / f"{job['id']}.old.svg").read_text(encoding='utf-8')
            crop = json.loads((tmp / f"{job['id']}.old.svg.json").read_text(encoding='utf-8'))['crop']
            s = score(flatten(img), shown(svg, crop, img.size))
            n = now[set_name][stem]
            out[f'{set_name}:{stem}'] = {
                'category': n['category'], 'preset': job['preset'],
                '1.6.0': {k: s[k] for k in ('similarity', 'defects', 'psnr', 'ssim')} | {'bytes': len(svg.encode())},
                'now': {k: n[k] for k in ('similarity', 'defects', 'psnr', 'ssim', 'bytes')}}
            print(f'{set_name}:{stem}', out[f'{set_name}:{stem}']['1.6.0']['similarity'], '->', n['similarity'], flush=True)
    (RESULTS / 'versions.json').write_text(json.dumps(out, indent=1), encoding='utf-8')
    return 0


if __name__ == '__main__':
    sys.exit(main())
