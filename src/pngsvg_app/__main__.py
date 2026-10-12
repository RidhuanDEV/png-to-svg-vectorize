"""python -m pngsvg_app [--port N] [--token T] [--no-browser]"""
from __future__ import annotations

import argparse
import multiprocessing
import sys


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog='png2svg serve', description='Run the PNG to SVG Vectorize UI locally '
                                 '(127.0.0.1 only; nothing is uploaded anywhere).')
    ap.add_argument('--port', type=int, default=0, help='port (default: a free random port)')
    ap.add_argument('--token', help='access token (default: random per session)')
    ap.add_argument('--no-browser', action='store_true', help='do not open the browser')
    ap.add_argument('-j', '--jobs', type=int, help='worker processes (default: min(4, CPUs))')
    a = ap.parse_args(argv)
    from . import serve
    serve(a.port, a.token, not a.no_browser, a.jobs)
    return 0


if __name__ == '__main__':
    multiprocessing.freeze_support()
    sys.exit(main())
