"""Other output formats from the engine's own SVG: PDF, EPS (print, design tools) and DXF (CAD, laser, plotters).

Only the SVG subset `vectorize` writes is read: <path> (M/L/C/Q/Z, absolute or relative), <rect>, solid colors and
userSpaceOnUse linear/radial gradients with stops. Gradients stay real gradients in PDF and EPS (PostScript level 3
shadings); DXF has no fills, so every shape becomes a closed polyline on a layer named after its color.
"""
from __future__ import annotations

import re
import zlib
from dataclasses import dataclass, field

FORMATS = ('svg', 'pdf', 'eps', 'dxf')
MEDIA_TYPES = {'svg': 'image/svg+xml', 'pdf': 'application/pdf', 'eps': 'application/postscript',
               'dxf': 'image/vnd.dxf'}

_NUM = re.compile(r'[MLCQZHVmlcqzhv]|-?(?:\d*\.\d+|\d+)(?:e-?\d+)?')
_ATTR = re.compile(r'([\w:-]+)="([^"]*)"')
_TAG = re.compile(r'<(/?)(\w+)([^>]*?)(/?)>')

Point = tuple[float, float]
# one sub-path: start point and segments; a segment is ('L', p) or ('C', c1, c2, p)
SubPath = tuple[Point, list[tuple]]


@dataclass
class Gradient:
    kind: str                                  # 'linear' | 'radial'
    stops: list[tuple[float, tuple[float, float, float]]]
    coords: tuple[float, ...] = ()             # linear: x1 y1 x2 y2
    matrix: tuple[float, ...] = (1, 0, 0, 1, 0, 0)   # radial: unit circle -> ellipse


@dataclass
class Shape:
    paths: list[SubPath]
    fill: tuple[float, float, float] | Gradient
    evenodd: bool = False
    stroke: float = 0.0                        # seam width (stroke in the fill color)
    layer: str = 'fill'


@dataclass
class Drawing:
    width: float
    height: float
    shapes: list[Shape] = field(default_factory=list)


def _rgb(h: str) -> tuple[float, float, float]:
    h = h.lstrip('#')
    return int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255


def _hex(c: tuple[float, float, float]) -> str:
    return '#' + ''.join(f'{round(v * 255):02X}' for v in c)


def parse_path(d: str) -> list[SubPath]:
    tokens = _NUM.findall(d)
    out: list[SubPath] = []
    cur: list[tuple] | None = None
    x = y = sx = sy = 0.0
    i, cmd = 0, ''
    while i < len(tokens):
        if tokens[i].isalpha():
            cmd = tokens[i]
            i += 1
            if cmd in 'Zz':
                x, y = sx, sy
                cur = None
                continue
        rel = cmd.islower()
        c = cmd.upper()
        n = {'M': 2, 'L': 2, 'C': 6, 'Q': 4, 'H': 1, 'V': 1}[c]
        v = [float(t) for t in tokens[i:i + n]]
        i += n
        if c == 'H':
            v = [v[0] + (x if rel else 0), y]
            rel, c = False, 'L'
        elif c == 'V':
            v = [x, v[0] + (y if rel else 0)]
            rel, c = False, 'L'
        pts = [(v[k] + (x if rel else 0), v[k + 1] + (y if rel else 0)) for k in range(0, len(v), 2)]
        if c == 'M':
            sx, sy = pts[0]
            cur = []
            out.append(((sx, sy), cur))
            cmd = 'l' if rel else 'L'        # further pairs after a move are line-tos
        else:
            if cur is None:                  # drawing after Z continues from the sub-path start
                cur = []
                out.append(((x, y), cur))
            if c == 'L':
                cur.append(('L', pts[0]))
            elif c == 'C':
                cur.append(('C', pts[0], pts[1], pts[2]))
            else:                            # quadratic -> cubic
                (qx, qy), p = pts
                cur.append(('C', (x + 2 / 3 * (qx - x), y + 2 / 3 * (qy - y)),
                            (p[0] + 2 / 3 * (qx - p[0]), p[1] + 2 / 3 * (qy - p[1])), p))
        x, y = pts[-1]
    return out


def parse_svg(svg: str) -> Drawing:
    """Read an SVG produced by `vectorize` (not arbitrary SVG)."""
    vb = re.search(r'viewBox="([^"]+)"', svg)
    if not vb:
        raise ValueError('not an SVG from this engine (no viewBox)')
    _, _, w, h = (float(v) for v in vb.group(1).split())
    drawing = Drawing(w, h)
    grads: dict[str, Gradient] = {}
    current: Gradient | None = None
    groups: list[dict[str, str]] = []
    for m in _TAG.finditer(svg):
        closing, tag, attrs, selfclose = m.groups()
        a = dict(_ATTR.findall(attrs))
        if closing:
            if tag == 'g' and groups:
                groups.pop()
            continue
        if tag == 'g':
            groups.append(a)
        elif tag in ('linearGradient', 'radialGradient'):
            if tag == 'linearGradient':
                current = Gradient('linear', [], tuple(float(a[k]) for k in ('x1', 'y1', 'x2', 'y2')))
            else:
                mat = re.search(r'matrix\(([^)]+)\)', a.get('gradientTransform', ''))
                current = Gradient('radial', [], matrix=tuple(float(v) for v in re.split(r'[ ,]+', mat.group(1).strip()))
                                   if mat else (1, 0, 0, 1, 0, 0))
            grads[a['id']] = current
        elif tag == 'stop' and current is not None:
            off = a.get('offset', '0')
            current.stops.append((float(off.rstrip('%')) / (100 if off.endswith('%') else 1), _rgb(a['stop-color'])))
        elif tag in ('path', 'rect'):
            inherited: dict[str, str] = {}
            for g in groups:
                inherited.update(g)
            fill = a.get('fill') or inherited.get('fill', '#000000')
            if fill == 'none':
                continue
            ref = re.match(r'url\(#([^)]+)\)', fill)
            paint = grads[ref.group(1)] if ref else _rgb(fill)
            if tag == 'rect':
                rw, rh = float(a['width']), float(a['height'])
                rx, ry = float(a.get('x', 0)), float(a.get('y', 0))
                paths = [((rx, ry), [('L', (rx + rw, ry)), ('L', (rx + rw, ry + rh)), ('L', (rx, ry + rh))])]
            else:
                paths = parse_path(a['d'])
            stroke = float(inherited.get('stroke-width', '0')) if 'stroke' in a else 0.0
            layer = next((g['id'] for g in reversed(groups) if 'id' in g), 'fill')
            drawing.shapes.append(Shape(paths, paint, a.get('fill-rule') == 'evenodd', stroke, layer))
    return drawing


def _f(v: float) -> str:
    s = f'{v:.3f}'.rstrip('0').rstrip('.')
    return '0' if s in ('', '-0') else s


def _mid_color(paint) -> tuple[float, float, float]:
    return paint if isinstance(paint, tuple) else paint.stops[len(paint.stops) // 2][1]


# ---------------------------------------------------------------------------------------------------------- PDF/EPS

def _path_ops(paths: list[SubPath], ps: bool) -> str:
    m, l, c, h = ('moveto', 'lineto', 'curveto', 'closepath') if ps else ('m', 'l', 'c', 'h')
    out = []
    for (x0, y0), segs in paths:
        out.append(f'{_f(x0)} {_f(y0)} {m}')
        for s in segs:
            if s[0] == 'L':
                out.append(f'{_f(s[1][0])} {_f(s[1][1])} {l}')
            else:
                out.append(' '.join(f'{_f(p[0])} {_f(p[1])}' for p in s[1:]) + f' {c}')
        out.append(h)
    return '\n'.join(out)


def _function(stops, ps: bool) -> str:
    """Stitching function over the gradient stops (each piece interpolates linearly between two colors)."""
    stops = sorted(stops)
    if stops[0][0] > 0:
        stops = [(0.0, stops[0][1])] + stops
    if stops[-1][0] < 1:
        stops = stops + [(1.0, stops[-1][1])]
    rgb = lambda c: ' '.join(_f(v) for v in c)  # noqa: E731
    parts = [f'<< /FunctionType 2 /Domain [0 1] /C0 [{rgb(a[1])}] /C1 [{rgb(b[1])}] /N 1 >>'
             for a, b in zip(stops, stops[1:])]
    bounds = ' '.join(_f(s[0]) for s in stops[1:-1])
    encode = ' '.join('0 1' for _ in parts)
    return (f'<< /FunctionType 3 /Domain [0 1] /Functions [{" ".join(parts)}] /Bounds [{bounds}] '
            f'/Encode [{encode}] >>')


def _shading(g: Gradient, ps: bool) -> str:
    if g.kind == 'linear':
        head = f'/ShadingType 2 /Coords [{" ".join(_f(v) for v in g.coords)}]'
    else:
        head = '/ShadingType 3 /Coords [0 0 0 0 0 1]'
    return f'<< {head} /ColorSpace /DeviceRGB /Function {_function(g.stops, ps)} /Extend [true true] >>'


def to_pdf(svg: str) -> bytes:
    d = parse_svg(svg)
    ops = [f'1 0 0 -1 0 {_f(d.height)} cm', '1 j']
    shadings: list[str] = []
    for s in d.shapes:
        path = _path_ops(s.paths, False)
        star = '*' if s.evenodd else ''
        if isinstance(s.fill, tuple):
            col = ' '.join(_f(v) for v in s.fill)
            if s.stroke:
                ops.append(f'{col} rg {col} RG {_f(s.stroke)} w\n{path}\nB{star}')
            else:
                ops.append(f'{col} rg\n{path}\nf{star}')
        else:
            name = f'/Sh{len(shadings)}'
            shadings.append(_shading(s.fill, False))
            cm = '' if s.fill.kind == 'linear' else ' '.join(_f(v) for v in s.fill.matrix) + ' cm '
            if s.stroke:
                col = ' '.join(_f(v) for v in _mid_color(s.fill))
                ops.append(f'{col} RG {_f(s.stroke)} w\n{path}\nS')
            ops.append(f'q\n{path}\nW{star} n\n{cm}{name} sh\nQ')
    content = zlib.compress('\n'.join(ops).encode('ascii'), 9)
    objs = [
        '<< /Type /Catalog /Pages 2 0 R >>',
        '<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
        (f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {_f(d.width)} {_f(d.height)}] /Contents 4 0 R '
         f'/Resources << /Shading << {" ".join(f"/Sh{i} {5 + i} 0 R" for i in range(len(shadings)))} >> >> >>'),
        None,  # content stream
        *shadings,
    ]
    out = bytearray(b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n')
    offsets = []
    for i, body in enumerate(objs, 1):
        offsets.append(len(out))
        if body is None:
            out += f'{i} 0 obj\n<< /Length {len(content)} /Filter /FlateDecode >>\nstream\n'.encode()
            out += content + b'\nendstream\nendobj\n'
        else:
            out += f'{i} 0 obj\n{body}\nendobj\n'.encode()
    xref = len(out)
    out += f'xref\n0 {len(objs) + 1}\n0000000000 65535 f \n'.encode()
    out += ''.join(f'{o:010d} 00000 n \n' for o in offsets).encode()
    out += f'trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode()
    return bytes(out)


def to_eps(svg: str) -> bytes:
    d = parse_svg(svg)
    w, h = d.width, d.height
    lines = ['%!PS-Adobe-3.0 EPSF-3.0', f'%%BoundingBox: 0 0 {int(-(-w // 1))} {int(-(-h // 1))}',
             f'%%HiResBoundingBox: 0 0 {_f(w)} {_f(h)}', '%%Creator: png-to-svg-vectorize', '%%LanguageLevel: 3',
             '%%EndComments', 'gsave', f'0 {_f(h)} translate 1 -1 scale', '1 setlinejoin']
    for s in d.shapes:
        path = 'newpath\n' + _path_ops(s.paths, True)
        fill = 'eofill' if s.evenodd else 'fill'
        clip = 'eoclip' if s.evenodd else 'clip'
        if isinstance(s.fill, tuple):
            col = ' '.join(_f(v) for v in s.fill) + ' setrgbcolor'
            stroke = f' gsave {fill} grestore {_f(s.stroke)} setlinewidth stroke' if s.stroke else f' {fill}'
            lines.append(f'{col}\n{path}\n{stroke.strip()}')
        else:
            if s.stroke:
                col = ' '.join(_f(v) for v in _mid_color(s.fill))
                lines.append(f'{col} setrgbcolor {_f(s.stroke)} setlinewidth\n{path}\nstroke')
            cm = '' if s.fill.kind == 'linear' else f'[{" ".join(_f(v) for v in s.fill.matrix)}] concat\n'
            lines.append(f'gsave\n{path}\n{clip}\n{cm}{_shading(s.fill, True)} shfill\ngrestore')
    lines += ['grestore', 'showpage', '%%EOF', '']
    return '\n'.join(lines).encode('ascii')


# ---------------------------------------------------------------------------------------------------------------- DXF

def _flatten(paths: list[SubPath], tol: float = 0.25) -> list[list[Point]]:
    """Polylines: cubic segments subdivided until the control polygon is within `tol` of the chord."""
    out = []
    for start, segs in paths:
        pts = [start]
        for s in segs:
            if s[0] == 'L':
                pts.append(s[1])
                continue
            p0, p1, p2, p3 = pts[-1], s[1], s[2], s[3]
            dev = max(abs((p1[0] - p0[0]) * (p3[1] - p0[1]) - (p1[1] - p0[1]) * (p3[0] - p0[0])),
                      abs((p2[0] - p0[0]) * (p3[1] - p0[1]) - (p2[1] - p0[1]) * (p3[0] - p0[0])))
            chord = max(((p3[0] - p0[0]) ** 2 + (p3[1] - p0[1]) ** 2) ** 0.5, 1e-9)
            n = max(1, min(64, int((dev / chord / tol) ** 0.5) + 1))
            for k in range(1, n + 1):
                t = k / n
                u = 1 - t
                pts.append((u ** 3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t ** 3 * p3[0],
                            u ** 3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t ** 3 * p3[1]))
        out.append(pts)
    return out


def to_dxf(svg: str) -> bytes:
    """AutoCAD R12 ASCII DXF: closed polylines, one layer per fill color (plus OUTLINE); y axis pointing up."""
    d = parse_svg(svg)
    ents: list[str] = []
    layers: list[str] = []
    for s in d.shapes:
        layer = 'OUTLINE' if s.layer == 'outline' else 'C' + _hex(_mid_color(s.fill))[1:]
        if layer not in layers:
            layers.append(layer)
        for pts in _flatten(s.paths):
            if len(pts) < 3:
                continue
            ents += ['0', 'POLYLINE', '8', layer, '66', '1', '70', '1']
            for x, y in pts:
                ents += ['0', 'VERTEX', '8', layer, '10', _f(x), '20', _f(d.height - y), '30', '0']
            ents += ['0', 'SEQEND', '8', layer]
    table = ['0', 'TABLE', '2', 'LAYER', '70', str(len(layers))]
    for name in layers:
        table += ['0', 'LAYER', '2', name, '70', '0', '62', '7', '6', 'CONTINUOUS']
    table += ['0', 'ENDTAB']
    head = ['0', 'SECTION', '2', 'HEADER', '9', '$ACADVER', '1', 'AC1009', '9', '$EXTMIN', '10', '0', '20', '0',
            '9', '$EXTMAX', '10', _f(d.width), '20', _f(d.height), '0', 'ENDSEC',
            '0', 'SECTION', '2', 'TABLES', *table, '0', 'ENDSEC', '0', 'SECTION', '2', 'ENTITIES']
    return ('\n'.join(head + ents + ['0', 'ENDSEC', '0', 'EOF']) + '\n').encode('ascii')


def convert(svg: str, fmt: str) -> bytes:
    if fmt == 'svg':
        return svg.encode('utf-8')
    if fmt == 'pdf':
        return to_pdf(svg)
    if fmt == 'eps':
        return to_eps(svg)
    if fmt == 'dxf':
        return to_dxf(svg)
    raise ValueError(f'unknown format {fmt!r}; choose one of: {", ".join(FORMATS)}')
