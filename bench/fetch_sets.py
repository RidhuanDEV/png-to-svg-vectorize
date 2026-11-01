"""Download the license-free comparison sets listed in bench/<set>/sources.json into bench/<set>/images.

    python bench/fetch_sets.py                 # E7: renders of CC0 vector art (bench/sets)
    python bench/fetch_sets.py --set real      # E8: pictures that were made as rasters (PNG / JPEG, bench/real)
    python bench/fetch_sets.py --update        # (maintainers) record hashes of freshly downloaded files
    python bench/fetch_sets.py --skip-changed  # (CI) leave out pictures Wikimedia now renders differently
    python bench/fetch_sets.py --sources-md    # regenerate bench/sets/SOURCES.md from the manifest

Every file is CC0 or public domain on Wikimedia Commons; title, author, license and page are in the manifest.
Images are not stored in git: they are downloaded on demand and checked against the recorded hash. Wikimedia
re-encodes its rendered thumbnails from time to time (same pixels, different bytes), so a file whose bytes changed is
still accepted when its decoded pixels match the recorded `pixels_sha256`.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.request
from pathlib import Path

BENCH = Path(__file__).resolve().parent
ROOT = BENCH / 'sets'
MANIFEST = ROOT / 'sources.json'
IMAGES = ROOT / 'images'
UA = 'png-to-svg-vectorize-bench/1.0 (https://github.com/RidhuanDEV/png-to-svg-vectorize)'


def download(url: str) -> bytes:
    for attempt in range(6):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA})
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001 - retried, then reported
            if attempt == 5:
                raise RuntimeError(f'download failed: {url}: {e}') from e
            time.sleep(3 * (attempt + 1))
    raise AssertionError('unreachable')


def pixels_sha256(data: bytes) -> str:
    """Hash of the decoded image (size, mode, pixels): what the benchmark actually reads."""
    import io

    from PIL import Image
    with Image.open(io.BytesIO(data)) as im:
        im.load()
        head = f'{im.size[0]}x{im.size[1]} {im.mode};'.encode()
        return hashlib.sha256(head + im.tobytes()).hexdigest()


def fetch(update: bool, skip_changed: bool = False) -> int:
    rows = json.loads(MANIFEST.read_text(encoding='utf-8'))
    IMAGES.mkdir(parents=True, exist_ok=True)
    bad = 0
    for row in rows:
        path = IMAGES / row['file']
        if path.exists() and not update:
            data = path.read_bytes()
        else:
            data = download(row['url'])
            time.sleep(0.5)                                  # be gentle with the Wikimedia servers
        digest = hashlib.sha256(data).hexdigest()
        if update:
            row['sha256'] = digest
            row['pixels_sha256'] = pixels_sha256(data)
        elif row.get('sha256') and digest not in (row['sha256'], *row.get('also_sha256', [])):
            # also_sha256: other renders Wikimedia serves for the same file (checked by hand, same bench result)
            if row.get('pixels_sha256') and row['pixels_sha256'] == pixels_sha256(data):
                print(f'{row["file"]}: re-encoded upstream, pixels identical')
            else:
                print(f'HASH MISMATCH {row["file"]}: expected {row["sha256"][:12]}…, got {digest[:12]}…',
                      file=sys.stderr)
                bad += 1
                continue
        path.write_bytes(data)
        print(f'{row["file"]:28s} {len(data) / 1024:7.0f} KB  {row["license"]}')
    if update:
        MANIFEST.write_text(json.dumps(rows, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    if bad and skip_changed and bad * 4 <= len(rows):
        # Wikimedia's thumbnail servers do not all render a file the same way: a picture whose render changed is left
        # out (the regression check compares only the pictures it has) rather than measured against a baseline made
        # from other pixels. Many changes at once are a real problem and still fail.
        print(f'{bad} picture(s) skipped: rendered differently upstream', file=sys.stderr)
        return 0
    return 1 if bad else 0


def sources_md() -> None:
    rows = json.loads(MANIFEST.read_text(encoding='utf-8'))
    command = 'python bench/fetch_sets.py' + ('' if ROOT.name == 'sets' else f' --set {ROOT.name}')
    lines = ['# Comparison set sources', '',
             'All images are **CC0 or public domain** on Wikimedia Commons. They are downloaded on demand by',
             f'`{command}` (not stored in this repository) and verified by SHA-256.', '',
             '| File | Category | Work (Commons page) | Author | License |', '|---|---|---|---|---|']
    for r in rows:
        title = r['title'].removeprefix('File:')
        lines.append(f"| `{r['file']}` | {r['category']} | [{title}]({r['page']}) | {r['artist'] or '—'} | "
                     f"{r['license']} |")
    (ROOT / 'SOURCES.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('wrote', ROOT / 'SOURCES.md')


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--update', action='store_true', help='re-download everything and record new hashes')
    ap.add_argument('--sources-md', action='store_true', help='regenerate SOURCES.md')
    ap.add_argument('--skip-changed', action='store_true',
                    help='leave out pictures whose upstream render changed (fails if more than a quarter did)')
    ap.add_argument('--set', default='sets', choices=['sets', 'real'], help='which set (default: sets = E7)')
    a = ap.parse_args(argv)
    global ROOT, MANIFEST, IMAGES
    ROOT = BENCH / a.set
    MANIFEST, IMAGES = ROOT / 'sources.json', ROOT / 'images'
    if a.sources_md:
        sources_md()
        return 0
    return fetch(a.update, a.skip_changed)


if __name__ == '__main__':
    sys.exit(main())
