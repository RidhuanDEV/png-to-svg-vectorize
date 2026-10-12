"""SVG path data encoding: compact relative commands with minimal number syntax."""
from __future__ import annotations

import re

_TOKEN = re.compile(r'[MLCQZmlcqz]|-?\d+(?:\.\d+)?')


def _num(v: float, decimals: int) -> str:
    s = f'{v:.{decimals}f}'.rstrip('0').rstrip('.') if decimals else str(int(round(v)))
    if s in ('-0', ''):
        return '0'
    if s.startswith('0.'):
        return s[1:]
    if s.startswith('-0.'):
        return '-' + s[2:]
    return s


def _join(nums: list[str]) -> str:
    """Join numbers with the fewest separators an SVG parser still reads unambiguously:
    '-' always starts a new number; '.5' starts a new number only if the previous one already has a '.'."""
    out, prev = '', ''
    for n in nums:
        if prev and not (n.startswith('-') or (n.startswith('.') and '.' in prev)):
            out += ' '
        out += n
        prev = n
    return out


def compact_path(d: str, dx: float = 0.0, dy: float = 0.0, scale: float = 1.0, decimals: int = 1) -> str:
    """Transform an absolute M/L/C/Q/Z path and re-encode it with relative commands and minimal number syntax
    (typically ~45% smaller than absolute coordinates). Rounding is done on absolute positions, so error
    never accumulates."""
    tokens = _TOKEN.findall(d)
    out: list[str] = []
    cx = cy = 0.0          # current point (rounded)
    sx = sy = 0.0          # sub-path start
    i = 0
    q = 10 ** decimals
    while i < len(tokens):
        cmd = tokens[i].upper()
        i += 1
        if cmd == 'Z':
            out.append('z')
            cx, cy = sx, sy
            continue
        arity = {'M': 2, 'L': 2, 'C': 6, 'Q': 4}[cmd]
        first = True
        while i < len(tokens) and not tokens[i].isalpha():
            vals = [float(t) for t in tokens[i:i + arity]]
            i += arity
            pts = [(round((vals[k] + dx) / scale * q) / q, round((vals[k + 1] + dy) / scale * q) / q)
                   for k in range(0, arity, 2)]
            if cmd == 'M' and first:
                if out:  # later sub-paths: relative move
                    out.append('m' + _join([_num(pts[0][0] - cx, decimals), _num(pts[0][1] - cy, decimals)]))
                else:
                    out.append('M' + _join([_num(pts[0][0], decimals), _num(pts[0][1], decimals)]))
                sx, sy = pts[0]
            else:
                letter = {'M': 'l', 'L': 'l', 'C': 'c', 'Q': 'q'}[cmd]
                nums = []
                for px, py in pts:
                    nums += [_num(px - cx, decimals), _num(py - cy, decimals)]
                out.append((letter if first or cmd == 'M' else ' ') + _join(nums))
            cx, cy = pts[-1]
            first = False
    return ''.join(out).replace('  ', ' ')

