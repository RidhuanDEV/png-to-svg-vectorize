"""Command line: png2svg INPUT (or python -m pngsvg INPUT) [INPUT ...] [-o OUT] [options]"""
from __future__ import annotations

import argparse
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from PIL import Image

from . import vectorize
from .compare import render, similarity
from .presets import PRESETS, options_for


def _options(a: argparse.Namespace, stem: str):
    opts = options_for(a.preset, id_prefix=stem)
    if a.scale is not None:
        opts.scale = a.scale
    if a.flat:
        opts.gradients = False
    if a.no_outline:
        opts.outlines = False
    if a.tolerance is not None:
        opts.tolerance = a.tolerance
    if a.smooth is not None:
        opts.smooth = a.smooth
    if a.merge_de is not None:
        opts.regions.merge_de = a.merge_de
    if a.core_de is not None:
        opts.outline.core_de = a.core_de
    return opts


def _convert(src: Path, dst: Path, opts, report: bool, executor=None) -> str:
    t = time.time()
    img = Image.open(src)
    res = vectorize(img, opts, executor=executor)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(res.svg, encoding='utf-8')
    line = (f'{src.name} -> {dst.name}: {res.regions} regions ({res.gradients} gradients), '
            f'{res.outline_paths} outline shapes, {dst.stat().st_size / 1024:.0f} KB, {time.time() - t:.1f}s')
    if report:
        r = render(res.svg, *img.size)
        line += ', similarity n/a (no Chrome/Edge found)' if r is None else \
            ', similarity {:.2f}% ({:.1f}% px within 24/255)'.format(*similarity(img, r))
    return line


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog='png2svg', description='Raster cartoon illustration -> pure-path SVG with '
                                 'gradient fills and crisp outlines.')
    ap.add_argument('inputs', nargs='+', type=Path, help='PNG/WebP/JPEG files')
    ap.add_argument('-o', '--out', type=Path, help='output file (single input) or directory (many inputs)')
    ap.add_argument('-p', '--preset', default='cartoon', choices=list(PRESETS),
                    help='; '.join(f'{k}: {v}' for k, v in PRESETS.items()))
    ap.add_argument('-j', '--jobs', type=int, default=0,
                    help='worker processes (default: auto = min(4, CPUs)); 1 = no parallelism')
    ap.add_argument('--scale', type=int, help='outline upscale factor for sub-pixel tracing (default: auto)')
    ap.add_argument('--tolerance', type=float, help='max curve deviation of fill boundaries in px (cartoon: 0.5); '
                    'higher = smaller file')
    ap.add_argument('--smooth', type=float, help='fill boundary smoothing in px (cartoon: 1.5)')
    ap.add_argument('--flat', action='store_true', help='flat colors instead of gradients')
    ap.add_argument('--no-outline', action='store_true', help='do not separate ink outlines')
    ap.add_argument('--merge-de', type=float, help='Delta E for merging soft-gradient regions (cartoon: 9)')
    ap.add_argument('--core-de', type=float, help='Delta E to ink color for pure outline pixels (default 9)')
    ap.add_argument('--report', action='store_true', help='render with headless Chrome/Edge and print similarity')
    a = ap.parse_args(argv)

    many = len(a.inputs) > 1 or (a.out is not None and a.out.suffix.lower() != '.svg')
    work = []
    for src in a.inputs:
        if a.out is None:
            dst = src.with_suffix('.svg')
        elif many:
            dst = a.out / (src.stem + '.svg')
        else:
            dst = a.out
        work.append((src, dst, _options(a, src.stem), a.report))

    jobs = a.jobs or min(4, os.cpu_count() or 1)
    if jobs <= 1:
        for w in work:
            print(_convert(*w), flush=True)
    elif len(work) == 1:                       # one image: parallel curve fitting
        with ProcessPoolExecutor(jobs) as ex:
            print(_convert(*work[0], executor=ex), flush=True)
    else:                                      # many images: one image per worker
        with ProcessPoolExecutor(min(jobs, len(work))) as ex:
            for line in ex.map(_convert, *zip(*work)):
                print(line, flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
