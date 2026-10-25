"""Command line: png2svg INPUT (or python -m pngsvg INPUT) [INPUT ...] [-o OUT] [options]

    png2svg serve [--port N] [--no-browser]     local web UI (needs the [app] extra)
"""
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
from .export import FORMATS, convert
from .presets import PRESETS, apply_overrides, options_for
from .profile import ProfileError, check_options, load


def _options(a: argparse.Namespace, stem: str):
    opts = options_for(a.preset, id_prefix=stem)
    apply_overrides(opts, a.profile_options)
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
    apply_overrides(opts, a.studio)
    return opts


def _convert(src: Path, dst: Path, opts, report: bool, executor=None) -> str:
    t = time.time()
    img = Image.open(src)
    res = vectorize(img, opts, executor=executor)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(convert(res.svg, dst.suffix[1:].lower()) if dst.suffix.lower() != '.svg'
                    else res.svg.encode('utf-8'))
    line = (f'{src.name} -> {dst.name}: {res.regions} regions ({res.gradients} gradients), '
            f'{res.outline_paths} outline shapes, {dst.stat().st_size / 1024:.0f} KB, {time.time() - t:.1f}s')
    if report:
        r = render(res.svg, *img.size)
        line += ', similarity n/a (no Chrome/Edge found)' if r is None else \
            ', similarity {:.2f}% ({:.1f}% px within 24/255)'.format(*similarity(img, r))
    return line


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    if argv[:1] == ['serve']:                  # png2svg serve [...]: local web UI
        try:
            from pngsvg_app.__main__ import main as serve_main
            import fastapi, uvicorn  # noqa: F401
        except ImportError:
            print('The UI needs the app extra: pip install "png-to-svg-vectorize[app]"', file=sys.stderr)
            return 2
        return serve_main(argv[1:])
    ap = argparse.ArgumentParser(prog='png2svg', description='Raster cartoon illustration -> pure-path SVG with '
                                 'gradient fills and crisp outlines.')
    ap.add_argument('inputs', nargs='+', type=Path, help='PNG/WebP/JPEG files')
    ap.add_argument('-o', '--out', type=Path, help='output file (single input) or directory (many inputs)')
    ap.add_argument('-p', '--preset', default=None, choices=list(PRESETS),
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
    st = ap.add_argument_group('studio options')
    st.add_argument('--profile', type=Path, help='style profile (.pngsvg-profile.json saved from the app); '
                    'other options on the command line override it')
    st.add_argument('-f', '--format', choices=FORMATS, help='output format (default: from -o, else svg)')
    st.add_argument('--max-colors', type=int, help='at most N flat colors (2-64), the ink included')
    st.add_argument('--palette', help='comma-separated colors to use, e.g. "#1F1B16,#D9472B,#FFFFFF"')
    st.add_argument('--color-mode', choices=('color', 'grayscale', 'bw'), help='bw = black and white')
    st.add_argument('--threshold', type=int, help='bw: gray level 1-254 below which a pixel is black (128)')
    st.add_argument('--remove-bg', action='store_true', help='leave the background out (transparent)')
    st.add_argument('--cutout', action='store_true', help='cut holes instead of stacking shapes (nothing overlaps)')
    st.add_argument('--seam', type=float, help='gap filler: stroke width painted around each fill (0-2, default .5)')
    st.add_argument('--speckle', type=int, help='merge spots smaller than N px into their neighbour (default 10)')
    a = ap.parse_args(argv)
    try:
        preset, a.profile_options = 'cartoon', {}
        if a.profile:
            preset, a.profile_options, _ = load(a.profile)
        a.preset = a.preset or preset
        a.studio = check_options({
            'max_colors': a.max_colors, 'color_mode': a.color_mode, 'threshold': a.threshold, 'seam': a.seam,
            'speckle': a.speckle, 'remove_bg': True if a.remove_bg else None,
            'layout': 'cutout' if a.cutout else None,
            'palette': [c.strip() for c in a.palette.split(',')] if a.palette else None})
    except (ProfileError, OSError) as e:
        ap.error(str(e))

    ext = '.' + (a.format or (a.out.suffix[1:].lower() if a.out is not None and a.out.suffix[1:].lower() in FORMATS
                              and len(a.inputs) == 1 else 'svg'))
    many = len(a.inputs) > 1 or (a.out is not None and a.out.suffix.lower()[1:] not in FORMATS)
    work = []
    for src in a.inputs:
        if a.out is None:
            dst = src.with_suffix(ext)
        elif many:
            dst = a.out / (src.stem + ext)
        else:
            dst = a.out if a.format is None else a.out.with_suffix(ext)
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
