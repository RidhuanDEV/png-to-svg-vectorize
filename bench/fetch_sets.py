"""Download the license-free comparison set (E7) listed in bench/sets/sources.json into bench/sets/images.

    python bench/fetch_sets.py                 # download missing files, verify SHA-256
    python bench/fetch_sets.py --update        # (maintainers) record hashes of freshly downloaded files
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

ROOT = Path(__file__).resolve().parent / 'sets'
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


def fetch(update: bool) -> int:
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
        elif row.get('sha256') and row['sha256'] != digest:
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
    return 1 if bad else 0


def sources_md() -> None:
    rows = json.loads(MANIFEST.read_text(encoding='utf-8'))
    lines = ['# Comparison set sources', '',
             'All images are **CC0 or public domain** on Wikimedia Commons. They are downloaded on demand by',
             '`python bench/fetch_sets.py` (not stored in this repository) and verified by SHA-256.', '',
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
    a = ap.parse_args(argv)
    if a.sources_md:
        sources_md()
        return 0
    return fetch(a.update)


if __name__ == '__main__':
    sys.exit(main())
