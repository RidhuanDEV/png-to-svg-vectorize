"""Optional: a vision-language model looks at every result and lists the defects it can see.

    python bench/readme.py                            # first: renders in bench/results/renders
    NVIDIA_API_KEY=nvapi-... python bench/judge.py    # NVIDIA NIM (build.nvidia.com); the key is never stored

Why: pixel scores average the error over the whole picture, so a lost color or a missing shape on a few percent of
the pixels barely moves them. A model that looks at the pictures reports such defects the way a person would. Its
weaknesses are as real: it can miss small things, invent defects, and vary from run to run. So the judge is
calibrated: CONTROL pairs with a known answer (identical pictures must score 10; pictures damaged on purpose must
score low) are judged with the same prompt, every pair is judged `--runs` times, and the agreement of its scores
with the pixel metrics is reported (Spearman). Only the license-free benchmark pictures are sent.

Output: bench/results/judge.json and judge.md.
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import os
import re
import statistics
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'bench'))
from evidence import fit, font, worst_box  # noqa: E402

RESULTS = ROOT / 'bench' / 'results'
URL = 'https://integrate.api.nvidia.com/v1/chat/completions'
MODEL = 'nvidia/nemotron-3.5-super-vl-120b-a12b'
PROMPT = (
    'You are checking a raster-to-vector conversion. In the top row, picture A (left) is the original and picture B '
    '(right) is the vector copy drawn back to pixels. The bottom row shows the same small area of A and B enlarged. '
    'Judge only how faithful B is to A: shapes, colors, missing or extra parts, outlines, gradients, text. Ignore '
    'tiny anti-aliasing differences along edges.\n'
    'Score 0-10: 10 = no visible difference; 8-9 = differences visible only in the enlarged area; 6-7 = small '
    'visible defects at normal size (a lost detail, a slightly wrong color in a small area); 3-5 = clear defects '
    '(missing shapes, merged colors, wrong gradients, holes); 0-2 = largely wrong.\n'
    'Reply with JSON only: {"score": <integer 0-10>, "defects": ["short description", ...]} (an empty list if none).')


def pair_image(a: Image.Image, b: Image.Image) -> bytes:
    """A | B on top, the area with the most error enlarged below, as JPEG."""
    cell, pad = 512, 12
    box = worst_box(a, b, max(32, min(a.size) // 6))
    canvas = Image.new('RGB', (2 * cell + 3 * pad, 2 * cell + 3 * pad + 30), (255, 255, 255))
    d = ImageDraw.Draw(canvas)
    for i, (im, label) in enumerate(((a, 'A original'), (b, 'B vector copy'))):
        x = pad + i * (cell + pad)
        d.text((x, 6), label, fill=(0, 0, 0), font=font(18))
        big = fit(im, cell, cell, Image.Resampling.LANCZOS)
        canvas.paste(big, (x + (cell - big.width) // 2, 30 + (cell - big.height) // 2))
        canvas.paste(fit(im.crop(box), cell, cell, Image.Resampling.NEAREST), (x, 30 + cell + pad))
    buf = io.BytesIO()
    canvas.save(buf, 'JPEG', quality=90)
    return buf.getvalue()


def ask(key: str, image: bytes, model: str, temperature: float) -> dict:
    body = {'model': model, 'temperature': temperature, 'max_tokens': 4096,
            'messages': [{'role': 'user', 'content': [
                {'type': 'text', 'text': PROMPT},
                {'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,' + base64.b64encode(image).decode()}}]}]}
    req = urllib.request.Request(URL, data=json.dumps(body).encode(), method='POST',
                                 headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json',
                                          'Accept': 'application/json'})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                reply = json.load(r)
            text = reply['choices'][0]['message'].get('content') or ''
            found = re.search(r'\{.*\}', text, re.S)
            parsed = json.loads(found.group(0)) if found else {}
            score = parsed.get('score')
            if isinstance(score, (int, float)) and 0 <= score <= 10:
                defects = [str(x) for x in parsed.get('defects', []) if str(x).strip()]
                return {'score': float(score), 'defects': defects}
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError) as e:
            code = getattr(e, 'code', '')
            print(f'  retry ({type(e).__name__} {code})', flush=True)    # never the request: it carries the key
        time.sleep(5 * (attempt + 1))
    return {'score': float('nan'), 'defects': ['no valid answer']}


def controls(renders: Path) -> list[tuple[str, str, Image.Image, Image.Image]]:
    """Pairs with a known answer: identical pictures, and pictures damaged on purpose."""
    out = []
    for set_name, stem in (('E7', 'cow'), ('E8', 'tux-flat'), ('E7', 'starry-night')):
        src = Image.open(renders / set_name / f'{stem}.source.png').convert('RGB')
        out.append((f'identical:{stem}', 'identical (expect 10)', src, src.copy()))
    src = Image.open(renders / 'E7' / 'icon-shop.source.png').convert('RGB')
    erased = src.copy()
    w, h = src.size
    ImageDraw.Draw(erased).rectangle((w * 0.55, h * 0.45, w * 0.8, h * 0.7), fill=(255, 255, 255))
    out.append(('erased:icon-shop', 'a part erased (expect <= 5)', src, erased))
    src = Image.open(renders / 'E8' / 'border-collie.source.png').convert('RGB')
    hsv = np.asarray(src.convert('HSV')).copy()
    hsv[..., 0] = (hsv[..., 0].astype(np.int16) + 40) % 256
    out.append(('hue:border-collie', 'colors shifted (expect <= 5)', src, Image.fromarray(hsv, 'HSV').convert('RGB')))
    src = Image.open(renders / 'E7' / 'shipment.source.png').convert('RGB')
    out.append(('posterized:shipment', '3 colors per channel (expect <= 6)', src,
                Image.fromarray((np.asarray(src) // 86 * 86 + 43).astype(np.uint8))))
    return out


def spearman(x: list[float], y: list[float]) -> float:
    from scipy.stats import spearmanr
    return float(spearmanr(x, y).statistic)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--runs', type=int, default=3)
    ap.add_argument('--model', default=MODEL)
    ap.add_argument('--temperature', type=float, default=0.3)
    ap.add_argument('--parallel', type=int, default=6, help='requests at the same time')
    a = ap.parse_args(argv)
    key = os.environ.get('NVIDIA_API_KEY', '').strip()
    if not key:
        print('set NVIDIA_API_KEY (https://build.nvidia.com)')
        return 2
    data = json.loads((RESULTS / 'readme.json').read_text(encoding='utf-8'))
    renders = RESULTS / 'renders'
    pairs = [(f'control:{cid}', what, x, y) for cid, what, x, y in controls(renders)]
    for set_name, rows in data['sets'].items():
        for stem in rows:
            pairs.append((f'{set_name}:{stem}', '', Image.open(renders / set_name / f'{stem}.source.png').convert('RGB'),
                          Image.open(renders / set_name / f'{stem}.svg.png').convert('RGB')))
    out = RESULTS / 'judge.json'
    results: dict = {'model': a.model, 'runs': a.runs, 'temperature': a.temperature, 'prompt': PROMPT, 'pairs': {}}
    if out.exists():                              # resume: keep pairs judged with the same model, prompt and runs
        old = json.loads(out.read_text(encoding='utf-8'))
        if all(old.get(k) == results[k] for k in ('model', 'runs', 'temperature', 'prompt')):
            results['pairs'] = {k: v for k, v in old.get('pairs', {}).items() if len(v.get('scores', [])) == a.runs}
    lock = threading.Lock()

    def judge_pair(pid: str, what: str, x: Image.Image, y: Image.Image) -> None:
        image = pair_image(x, y)
        answers = [ask(key, image, a.model, a.temperature) for _ in range(a.runs)]
        scores = [r['score'] for r in answers if r['score'] == r['score']]
        with lock:
            results['pairs'][pid] = {'expect': what, 'scores': scores,
                                     'median': statistics.median(scores) if scores else None,
                                     'defects': answers[0]['defects'] if answers else []}
            out.write_text(json.dumps(results, indent=1, ensure_ascii=False), encoding='utf-8')
            print(f'{pid:32s} {scores} {results["pairs"][pid]["defects"][:2]}', flush=True)

    todo = [p for p in pairs if p[0] not in results['pairs']]
    with ThreadPoolExecutor(a.parallel) as pool:  # each answer takes 15-60 s; the free tier allows 40 requests/min
        list(pool.map(lambda p: judge_pair(*p), todo))
    order = [p[0] for p in pairs]
    results['pairs'] = {k: results['pairs'][k] for k in order if k in results['pairs']}
    bench = [(pid.split(':', 1), r) for pid, r in results['pairs'].items() if not pid.startswith('control')]
    judged = [(data['sets'][s][stem], r['median']) for (s, stem), r in bench if r['median'] is not None]
    results['spearman'] = {
        'similarity': round(spearman([m['similarity'] for m, _ in judged], [j for _, j in judged]), 3),
        'defect_area': round(spearman([-m['defects'] for m, _ in judged], [j for _, j in judged]), 3),
        'ssim': round(spearman([m['ssim'] for m, _ in judged], [j for _, j in judged]), 3)}
    spread = [max(r['scores']) - min(r['scores']) for _, r in results['pairs'].items() if len(r['scores']) > 1]
    results['run_spread_median'] = statistics.median(spread) if spread else None
    out.write_text(json.dumps(results, indent=1, ensure_ascii=False), encoding='utf-8')
    lines = ['| Pair | Expected | Scores | Median | Defects it saw (first run) |', '|---|---|---|---|---|']
    for pid, r in results['pairs'].items():
        lines.append(f"| {pid} | {r['expect'] or '—'} | {', '.join(f'{s:g}' for s in r['scores'])} | "
                     f"{r['median'] if r['median'] is not None else '—'} | {'; '.join(r['defects'][:3]) or 'none'} |")
    lines.append('')
    lines.append(f"Spearman agreement of the judge's median with: similarity {results['spearman']['similarity']}, "
                 f"defect area (lower = better) {results['spearman']['defect_area']}, SSIM {results['spearman']['ssim']}. "
                 f"Median spread between runs: {results['run_spread_median']}.")
    (RESULTS / 'judge.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('\n'.join(lines[-1:]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
