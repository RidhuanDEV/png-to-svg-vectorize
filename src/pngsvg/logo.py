"""Flat logo / icon engine: clean, small, animatable SVG from flat-color artwork.

Stages (each a pure function on explicit types; same input + options -> byte-identical SVG):

    load -> background -> quantize -> assign (anti-alias aware) -> clean -> shapes -> contours -> fit -> serialize

1. load: RGB(A) as float, opacity; pictures under 256 px are traced at 2x.
2. background: transparent pixels, or else the dominant border color within a CIEDE2000 tolerance. It never becomes
   a <rect> or a path.
3. quantize: k-means in CIELAB (k-means++ start, fixed seed) on the flat (non-edge) pixels; automatic k = the
   smallest one whose mean error stays below the tolerance (at most 8); close clusters merged; or a fixed palette.
4. assign: every pixel is matched to the nearest MIX of two palette colors (anti-aliased edges are mixes) and takes
   the color that covers at least half of it, so edges neither grow nor shrink.
5. clean: 3x3 majority filter and speck removal (small pieces join their dominant neighbour).
6. shapes: one shape per 4-connected piece of one color; pieces joined only by a thin neck are split there.
7. contours: shared boundaries between shapes (planar map) placed at their sub-pixel position from anti-aliasing,
   so neighbours fit without gaps or overlap — no stroke tricks.
8. fit: sharp corners (> corner angle), straight runs as lines (snapped to 0/90 degrees and to each other's angles),
   the rest as cubic Beziers; optional uniform corner rounding.
9. serialize: one <path> per shape with a stable id and color class, viewBox trimmed to the content.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable

import numpy as np
from PIL import Image
from scipy import ndimage

from .color import delta_e2000, to_hex, to_lab
from .curves import _midpoints, _smooth_closed, _smooth_open, fit_curve
from .pathdata import _num
from .planar import Chain, build_chains, region_loops, subpixel_offsets

Point = tuple[float, float]


@dataclass
class LogoParams:
    """Settings of the flat engine (the shared Options carry max_colors, palette, remove_bg, decimals, layers)."""
    alpha_threshold: int = 16          # opacity (0-255) below which a pixel is background
    bg_tolerance: float = 6.0          # CIEDE2000 distance to the border color that still counts as background
    quant_tolerance: float = 4.0       # automatic colors: mean CIE76 error per pixel the palette must stay below
    merge_tolerance: float = 8.0       # palette colors closer than this (CIEDE2000) become one
    max_auto_colors: int = 8
    min_area_ratio: float = 0.0005     # specks: smaller than this share of the content area (and min_area px) go
    split_shapes: bool = True          # split one-color pieces joined only by a neck thinner than neck_width px
    neck_width: float = 3.0
    corner_angle: float = 35.0         # a turn sharper than this (degrees) is a corner and stays sharp
    line_tolerance: float = 1.0        # a run between corners within this distance (px) of a line becomes a line
    curve_tolerance: float = 0.8       # max distance (px) of a fitted curve from the traced boundary
    snap_angles: bool = True           # snap lines within 2 deg to horizontal/vertical, align lines within 1.5 deg
    corner_radius: float = 0.0         # > 0: round every sharp corner between two lines with this radius (px)
    trim: bool = True                  # viewBox = content bounding box (+ padding), coordinates start at 0,0
    padding: float = 0.0
    pixel: bool = False                # pixel art: follow the pixel grid exactly, no smoothing
    name: str = 'logo'                 # id of the group that holds the shapes
    title: str = ''                    # optional <title>


@dataclass
class Background:
    mask: np.ndarray                   # (h, w) bool
    color: np.ndarray                  # (3,) sRGB 0-255


@dataclass
class Palette:
    rgb: np.ndarray                    # (k, 3) sRGB 0-255, largest area first
    warnings: list[str]


@dataclass
class Shapes:
    label: np.ndarray                  # (h, w) int: 1..n shapes, n + 1 background
    color: list[int]                   # palette index per shape (index 0 unused)
    order: list[int]                   # shape labels sorted top-left to bottom-right


@dataclass
class Segment:
    kind: str                          # 'L' line, 'C' cubic, 'Q' quadratic (rounded corner)
    points: list[Point]                # start, [controls...], end

    def reversed(self) -> Segment:
        return Segment(self.kind, self.points[::-1])


@dataclass
class LogoResult:
    svg: str
    shapes: int
    palette: list[str]
    crop: tuple[float, float, float, float]    # x, y, width, height of the viewBox in picture pixels
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------------------------------- 1. load

def load(image: Image.Image, upscale_below: int = 256) -> tuple[np.ndarray, np.ndarray | None, int]:
    """(rgb float 0-255 composited on white, opacity 0-1 or None, trace scale)."""
    rgba = np.asarray(image.convert('RGBA'), np.float64)
    alpha = rgba[..., 3] / 255
    rgb = rgba[..., :3] * alpha[..., None] + 255 * (1 - alpha[..., None])
    has_alpha = bool((alpha < 0.999).any())
    scale = 2 if max(image.size) < upscale_below else 1
    if scale > 1:
        size = (image.width * scale, image.height * scale)
        rgb = np.asarray(Image.fromarray(np.clip(rgb + 0.5, 0, 255).astype(np.uint8)).resize(size, Image.Resampling.LANCZOS),
                         np.float64)
        if has_alpha:
            a8 = Image.fromarray(np.clip(alpha * 255 + 0.5, 0, 255).astype(np.uint8))
            alpha = np.asarray(a8.resize(size, Image.Resampling.LANCZOS), np.float64) / 255
    return rgb, (alpha if has_alpha else None), scale


# ---------------------------------------------------------------------------------------------- 2. background

def background(rgb: np.ndarray, alpha: np.ndarray | None, p: LogoParams, keep: bool) -> Background:
    h, w = rgb.shape[:2]
    if keep:
        return Background(np.zeros((h, w), bool), np.array([255.0, 255.0, 255.0]))
    if alpha is not None and (alpha * 255 < p.alpha_threshold).any():
        return Background(alpha * 255 < p.alpha_threshold, np.array([255.0, 255.0, 255.0]))
    k = max(2, min(4, min(h, w) // 50))
    border = np.concatenate([rgb[:k].reshape(-1, 3), rgb[-k:].reshape(-1, 3),
                             rgb[k:-k, :k].reshape(-1, 3), rgb[k:-k, -k:].reshape(-1, 3)])
    bins = (border // 8).astype(np.int64)
    key = (bins[:, 0] << 10) | (bins[:, 1] << 5) | bins[:, 2]
    vals, counts = np.unique(key, return_counts=True)
    top = vals[int(np.argmax(counts))]
    color = border[key == top].mean(axis=0)
    if counts.max() < 0.3 * len(border):        # no dominant border color: nothing is background
        return Background(np.zeros((h, w), bool), color)
    lab = to_lab(rgb)
    ref = to_lab(color)
    near = np.linalg.norm(lab - ref, axis=-1) < 3 * p.bg_tolerance        # cheap pre-filter (CIE76)
    mask = np.zeros((h, w), bool)
    mask[near] = delta_e2000(lab[near], ref) <= p.bg_tolerance
    return Background(mask, color)


# ---------------------------------------------------------------------------------------------- 3. quantize

def _kmeans(x: np.ndarray, k: int, seed: int = 0, iters: int = 40) -> tuple[np.ndarray, np.ndarray]:
    """k-means++ in Lab with a fixed seed. Returns (centers, labels)."""
    rng = np.random.default_rng(seed)
    centers = [x[int(rng.integers(len(x)))]]
    d2 = np.full(len(x), np.inf)
    for _ in range(1, k):
        d2 = np.minimum(d2, ((x - centers[-1]) ** 2).sum(1))
        total = d2.sum()
        if total <= 0:
            break
        centers.append(x[int(rng.choice(len(x), p=d2 / total))])
    c = np.array(centers)
    lab = np.zeros(len(x), np.int64)
    for _ in range(iters):
        lab = np.argmin(((x[:, None] - c[None]) ** 2).sum(-1), 1)
        new = np.array([x[lab == j].mean(0) if (lab == j).any() else c[j] for j in range(len(c))])
        if np.allclose(new, c, atol=1e-4):
            break
        c = new
    return c, lab


def flat_pixels(rgb: np.ndarray, mask: np.ndarray, limit: int = 120_000) -> np.ndarray:
    """Foreground pixels away from edges (no neighbour differs by more than 12 levels), evenly subsampled."""
    d = np.zeros(rgb.shape[:2])
    for axis in (0, 1):
        diff = np.abs(np.diff(rgb, axis=axis)).max(-1)
        pad = [(0, 0), (0, 0)]
        pad[axis] = (1, 0)
        d = np.maximum(d, np.pad(diff, pad))
        pad[axis] = (0, 1)
        d = np.maximum(d, np.pad(diff, pad))
    pick = rgb[mask & (d <= 12)]
    if len(pick) < 64:
        pick = rgb[mask]
    step = max(1, len(pick) // limit)
    return pick[::step]


def quantize(rgb: np.ndarray, fg: np.ndarray, p: LogoParams, max_colors: int | None,
             palette: tuple[str, ...] | None) -> Palette:
    warnings: list[str] = []
    if palette:
        fixed = np.array([[int(h[i:i + 2], 16) for i in (1, 3, 5)] for h in palette], np.float64)
        return Palette(fixed, warnings)
    sample = flat_pixels(rgb, fg)
    if len(sample) == 0:
        return Palette(np.zeros((0, 3)), ['no foreground found'])
    lab = to_lab(sample).astype(np.float64)
    if max_colors:
        centers, assign = _kmeans(lab, max_colors)
    else:
        for k in range(1, p.max_auto_colors + 1):
            centers, assign = _kmeans(lab, k)
            err = float(np.linalg.norm(lab - centers[assign], axis=1).mean())
            if err < p.quant_tolerance:
                break
        else:
            warnings.append(f'more than {p.max_auto_colors} colors (mean error {err:.1f}): this picture is not a flat '
                            'logo; the illustration or cartoon style keeps more detail')
    # merge near-identical clusters (weighted by size)
    groups: list[list[int]] = []
    for j in np.argsort(-np.bincount(assign, minlength=len(centers))):
        for g in groups:
            if float(delta_e2000(centers[g[0]], centers[j])) < p.merge_tolerance:
                g.append(int(j))
                break
        else:
            groups.append([int(j)])
    out, sizes = [], []
    for g in groups:
        sel = np.isin(assign, g)
        if sel.any():
            out.append(sample[sel].mean(0))
            sizes.append(int(sel.sum()))
    order = np.argsort(-np.array(sizes), kind='stable')
    centers_rgb = np.round(np.array(out)[order])
    allfg = rgb[fg][::max(1, int(fg.sum()) // 60_000)]
    if len(allfg) and not warnings:
        err_all = float(np.linalg.norm(to_lab(allfg)[:, None] - to_lab(centers_rgb)[None], axis=-1).min(1).mean())
        if err_all > 2 * p.quant_tolerance:
            warnings.append(f'the picture has shading or many colors (mean error {err_all:.0f}): it is not a flat '
                            'logo; the illustration or cartoon style keeps more detail')
    return Palette(centers_rgb, warnings)


# ------------------------------------------------------------------------------------------------ 4. assign

def assign(rgb: np.ndarray, bg: Background, pal: Palette, chunk: int = 1 << 18) -> np.ndarray:
    """Label per pixel: 0..k-1 palette colors, k background. Each pixel is matched to the closest mix t*A + (1-t)*B
    of two colors (a pure color is t = 1) and takes A if it covers at least half of the pixel."""
    h, w = rgb.shape[:2]
    k = len(pal.rgb)
    colors = np.vstack([pal.rgb, bg.color[None]])
    out = np.full(h * w, k, np.int64)
    flat = rgb.reshape(-1, 3)
    todo = np.nonzero(~bg.mask.ravel())[0]
    pairs = [(i, j) for i in range(len(colors)) for j in range(i + 1, len(colors))] or [(0, 0)]
    for s in range(0, len(todo), chunk):
        idx = todo[s:s + chunk]
        px = flat[idx]
        best = np.full(len(idx), np.inf)
        pick = np.zeros(len(idx), np.int64)
        for i, j in pairs:
            a, b = colors[i], colors[j]
            ab = a - b
            den = float(ab @ ab)
            t = np.clip(((px - b) @ ab) / den, 0, 1) if den > 0 else np.ones(len(idx))
            res = ((px - (b + t[:, None] * ab)) ** 2).sum(1)
            better = res < best
            best[better] = res[better]
            pick[better] = np.where(t[better] >= 0.5, i, j)
        out[idx] = pick
    return out.reshape(h, w)


# ------------------------------------------------------------------------------------------------- 5. clean

def majority(label: np.ndarray, n_labels: int) -> np.ndarray:
    """3x3 majority filter: a pixel takes the label held by at least 5 of its 9 pixels (else it is kept)."""
    best = np.zeros(label.shape)
    win = label.copy()
    for v in range(n_labels):
        c = ndimage.uniform_filter((label == v).astype(np.float64), 3, mode='nearest') * 9
        take = c > best
        best[take] = c[take]
        win[take] = v
    return np.where(best >= 4.5, win, label)


def remove_specks(label: np.ndarray, n_labels: int, min_area: int) -> np.ndarray:
    """Pieces smaller than min_area take the label most common around them (repeated until stable)."""
    out = label.copy()
    for _ in range(4):
        changed = False
        for v in range(n_labels):
            comp, n = ndimage.label(out == v)
            if not n:
                continue
            sizes = np.bincount(comp.ravel())
            boxes = ndimage.find_objects(comp)
            for c in np.nonzero(sizes < min_area)[0]:
                box = boxes[c - 1] if c > 0 else None
                if box is None:
                    continue
                sl = tuple(slice(max(0, b.start - 1), b.stop + 1) for b in box)
                piece = comp[sl] == c
                ring = ndimage.binary_dilation(piece) & ~piece
                around = out[sl][ring]
                if len(around):
                    out[sl][piece] = np.bincount(around, minlength=n_labels).argmax()
                    changed = True
        if not changed:
            break
    return out


# ------------------------------------------------------------------------------------------------ 6. shapes

def split_necks(piece: np.ndarray, neck: float) -> np.ndarray:
    """Labels 1..m of a one-color piece split where it is thinner than `neck` px (thin parts stay with the nearest
    thick part)."""
    r = max(1, int(round(neck / 2)))
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
    disk = xx * xx + yy * yy <= r * r
    cores, m = ndimage.label(ndimage.binary_opening(piece, structure=disk))
    if m < 2:
        return piece.astype(np.int64)
    _, (iy, ix) = ndimage.distance_transform_edt(cores == 0, return_indices=True)
    return np.where(piece, cores[iy, ix], 0)


def shapes(label: np.ndarray, k: int, p: LogoParams) -> Shapes:
    h, w = label.shape
    out = np.zeros((h, w), np.int64)
    color = [0]
    cents: list[tuple[float, float]] = [(0.0, 0.0)]
    big = max(16.0, (2 * p.neck_width) ** 2)
    for c in range(k):
        comp, n = ndimage.label(label == c)
        for i, box in enumerate(ndimage.find_objects(comp), start=1):
            if box is None:
                continue
            piece = comp[box] == i
            split = p.split_shapes and not p.pixel and piece.sum() > 4 * big
            parts = split_necks(piece, p.neck_width) if split else piece.astype(np.int64)
            region = out[box]
            for j in range(1, int(parts.max()) + 1):
                sel = parts == j
                if not sel.any():
                    continue
                region[sel] = len(color)
                ys, xs = np.nonzero(sel)
                color.append(c)
                cents.append((float(ys.mean()) + box[0].start, float(xs.mean()) + box[1].start))
    n_shapes = len(color) - 1
    out[out == 0] = n_shapes + 1                         # background
    band = max(1.0, 0.08 * h)                            # rows of 8 % height, then left to right
    order = sorted(range(1, n_shapes + 1), key=lambda s: (round(cents[s][0] / band), cents[s][1], s))
    return Shapes(out, color, order)


# ---------------------------------------------------------------------------------------------- 7. contours

def contours(sh: Shapes, rgb: np.ndarray, pal: Palette, bg: Background, p: LogoParams) -> tuple[list[Chain], list[np.ndarray]]:
    """Shared boundary chains and, per chain, its polyline at the sub-pixel edge position."""
    chains = build_chains(sh.label)
    n = len(sh.color)
    mean = np.zeros((n + 1, 3))
    for s in range(1, n):
        mean[s] = pal.rgb[sh.color[s]]
    mean[n] = bg.color
    polys = []
    for c in chains:
        if p.pixel:
            polys.append(c.points.astype(np.float64))
            continue
        off = subpixel_offsets(c, sh.label, rgb, mean, None, min_contrast=20.0)
        polys.append(_midpoints(c.points, c.closed, off))
    return chains, polys


# --------------------------------------------------------------------------------------------------- 8. fit

@dataclass
class _Line:
    centre: np.ndarray
    direction: np.ndarray       # unit
    length: float


@dataclass
class _Run:
    """Part of a chain between two corners: a line, or points for curve fitting."""
    start: int
    end: int
    line: _Line | None


@dataclass
class _ChainFit:
    closed: bool
    pts: np.ndarray
    corners: list[int]          # indices into pts (open chains: include both ends)
    runs: list[_Run]


def _turns(p: np.ndarray, closed: bool, window: int) -> np.ndarray:
    n = len(p)
    if closed:
        a, b = np.roll(p, window, 0), np.roll(p, -window, 0)
        v1, v2 = p - a, b - p
    else:
        idx = np.arange(n)
        v1 = p - p[np.clip(idx - window, 0, n - 1)]
        v2 = p[np.clip(idx + window, 0, n - 1)] - p
    n1 = np.linalg.norm(v1, axis=1)
    n2 = np.linalg.norm(v2, axis=1)
    cos = (v1 * v2).sum(1) / np.maximum(n1 * n2, 1e-9)
    turn = np.degrees(np.arccos(np.clip(cos, -1, 1)))
    if not closed:
        turn[:window] = 0
        turn[n - window:] = 0
    return turn


def _fit_line(pts: np.ndarray) -> tuple[_Line, float]:
    centre = pts.mean(0)
    cov = np.cov((pts - centre).T) if len(pts) > 2 else np.outer(pts[-1] - pts[0], pts[-1] - pts[0])
    vals, vecs = np.linalg.eigh(cov)
    d = vecs[:, int(np.argmax(vals))]
    if float(d @ (pts[-1] - pts[0])) < 0:
        d = -d
    normal = np.array([-d[1], d[0]])
    dev = float(np.abs((pts - centre) @ normal).max()) if len(pts) else 0.0
    proj = (pts - centre) @ d
    return _Line(centre, d, float(proj.max() - proj.min()) if len(pts) else 0.0), dev


def _circle_fit(pts: np.ndarray) -> tuple[float, float]:
    """(max distance of the points from their least-squares circle, its radius) — Kasa fit; (inf, inf) if none."""
    x, y = pts[:, 0] - pts[:, 0].mean(), pts[:, 1] - pts[:, 1].mean()
    a = np.column_stack([x, y, np.ones(len(x))])
    sol, *_ = np.linalg.lstsq(a, x * x + y * y, rcond=None)
    cx, cy = sol[0] / 2, sol[1] / 2
    r2 = sol[2] + cx * cx + cy * cy
    if not np.isfinite(r2) or r2 <= 0:
        return math.inf, math.inf
    r = math.sqrt(r2)
    return float(np.abs(np.hypot(x - cx, y - cy) - r).max()), r


def _run_points(pts: np.ndarray, start: int, end: int) -> np.ndarray:
    """Points of a run from corner index `start` to `end` (wrapping around a closed chain)."""
    if end > start:
        return pts[start:end + 1]
    return np.vstack([pts[start:], pts[:end + 1]])


def _douglas_peucker(pts: np.ndarray, closed: bool, tol: float) -> list[int]:
    """Indices of the Douglas-Peucker vertices (closed chains: split at the point farthest from the start)."""
    n = len(pts)
    ext = np.vstack([pts, pts[:1]]) if closed else pts
    far = int(np.argmax(np.linalg.norm(pts - pts[0], axis=1))) if closed else n - 1
    keep = {0, far, len(ext) - 1}
    stack = [(0, far), (far, len(ext) - 1)] if closed else [(0, n - 1)]
    while stack:
        a, b = stack.pop()
        if b <= a + 1:
            continue
        seg = ext[a:b + 1]
        d = ext[b] - ext[a]
        length = float(np.hypot(d[0], d[1]))
        rel = seg - ext[a]
        dist = np.abs(d[0] * rel[:, 1] - d[1] * rel[:, 0]) / length if length > 1e-9 else np.hypot(rel[:, 0], rel[:, 1])
        k = int(np.argmax(dist))
        if dist[k] > tol:
            keep.add(a + k)
            stack += [(a, a + k), (a + k, b)]
    return sorted({i % n for i in keep})


def _span(n: int, a: int, b: int, closed: bool) -> int:
    return (b - a) % n if closed else b - a


def _parallel(a: _Run, b: _Run, degrees: float) -> bool:
    return a.line is not None and b.line is not None and \
        abs(float(a.line.direction @ b.line.direction)) > math.cos(math.radians(degrees))


def _straight_runs(pts: np.ndarray, closed: bool, p: LogoParams, window: int) -> list[_Run]:
    """Long straight runs: Douglas-Peucker pieces that a line fits within line_tolerance (their ends may be the arcs
    of slightly rounded corners and are not judged). Collinear neighbours are joined; runs that only continue a
    gentle bend on both sides (a polygonised circle) are not lines."""
    verts = _douglas_peucker(pts, closed, p.line_tolerance)
    pairs = list(zip(verts, verts[1:] + ([verts[0]] if closed else [])))
    min_len = max(8.0, 2.0 * window)
    lines: list[_Run] = []
    for k, (a, b) in enumerate(pairs):
        chord = float(np.linalg.norm(pts[b] - pts[a]))
        if chord < min_len:
            continue
        seg = _run_points(pts, a, b)
        trim = min(window, max(0, (len(seg) - 3) // 4))
        line, dev = _fit_line(seg[trim:len(seg) - trim] if trim else seg)
        if dev > p.line_tolerance:
            continue
        # a chord of an arc passes the line test too: if this piece and both its neighbours lie on one circle of a
        # sensible radius, it is part of a curve (a corner between two lines never fits one circle)
        if closed or 0 < k < len(pairs) - 1:
            lo, hi = pairs[k - 1][0], pairs[(k + 1) % len(pairs)][1]
            around = _run_points(pts, lo, hi) if lo != hi else pts
            res, radius = _circle_fit(around)
            span = float(np.linalg.norm(around[-1] - around[0])) + chord
            if res <= p.line_tolerance and radius < 3 * span:
                continue
        lines.append(_Run(a, b, line))
    merged: list[_Run] = []
    for r in lines:
        if merged and merged[-1].end == r.start and _parallel(merged[-1], r, 3):
            last = merged[-1]
            merged[-1] = _Run(last.start, r.end, _fit_line(_run_points(pts, last.start, r.end))[0])
        else:
            merged.append(r)
    if closed and len(merged) > 1 and merged[-1].end == merged[0].start and _parallel(merged[-1], merged[0], 3):
        a, b = merged[-1], merged[0]
        merged = [_Run(a.start, b.end, _fit_line(_run_points(pts, a.start, b.end))[0])] + merged[1:-1]
    out: list[_Run] = []
    m = len(merged)
    for i, r in enumerate(merged):
        gentle = []
        for j, touching in ((i - 1, i > 0 or closed), (i + 1, i + 1 < m or closed)):
            o = merged[j % m]
            if not touching or o is r:
                continue
            adjacent = o.end == r.start if j == i - 1 else r.end == o.start
            if adjacent:
                gentle.append(_parallel(o, r, 20))
        if len(gentle) == 2 and all(gentle):
            continue                           # bends gently on both sides: part of a curve
        out.append(r)
    return out


def _sharp_corners(turn: np.ndarray, a: int, b: int, closed: bool, window: int, angle: float) -> list[int]:
    """Sharp corners strictly inside the run a..b (turn measured over +-window points), non-max suppressed."""
    n = len(turn)
    length = _span(n, a, b, closed) if (b != a or not closed) else n
    idx = [(a + k) % n for k in range(1, length)]
    cand = sorted((i for i in idx if turn[i] > angle and (i - a) % n > window and (length - (i - a) % n) > window),
                  key=lambda i: -turn[i])
    picked: list[int] = []
    for c in cand:
        if all(min(abs(c - q), n - abs(c - q)) > 2 * window for q in picked):
            picked.append(c)
    return sorted(picked, key=lambda i: (i - a) % n)


def analyse(chain: Chain, pts: np.ndarray, p: LogoParams, window: int) -> _ChainFit:
    """Corners and runs of one chain: straight lines (meeting at sharp corners) and curves in between."""
    closed = chain.closed
    n = len(pts)
    if p.pixel:
        d = np.diff(np.vstack([pts, pts[:1]]) if closed else pts, axis=0)
        corners = [int(i) for i in np.nonzero(np.any(d[1:] != d[:-1], axis=1))[0] + 1]
        if closed and len(d) and np.any(d[0] != d[-1]):
            corners = [0] + corners
        if not closed:
            corners = sorted(set([0] + corners + [n - 1]))
        pairs = list(zip(corners, corners[1:] + ([corners[0]] if closed else [])))
        return _ChainFit(closed, pts, corners, [_Run(a, b, _Line(pts[a], np.zeros(2), 0.0)) for a, b in pairs])
    sm = _smooth_closed(pts, 1.0) if closed else _smooth_open(pts, 1.0)
    turn = _turns(sm, closed, window)
    lines = _straight_runs(pts, closed, p, window) if n > 2 * window else []
    short_gap = 4 * window
    runs: list[_Run] = []

    def curve(a: int, b: int) -> None:
        cuts = [a] + _sharp_corners(turn, a, b, closed, window, p.corner_angle) + [b]
        runs.extend(_Run(x, y, None) for x, y in zip(cuts, cuts[1:]))

    if not lines:
        if not closed:
            curve(0, n - 1)
            return _ChainFit(closed, pts, [r.start for r in runs] + [n - 1], runs)
        cuts = _sharp_corners(turn, 0, 0, True, window, p.corner_angle) if n > 4 * window else []
        if len(cuts) > 1:
            runs = [_Run(x, y, None) for x, y in zip(cuts, cuts[1:] + cuts[:1])]
        elif len(cuts) == 1:
            runs = [_Run(cuts[0], cuts[0], None)]
        return _ChainFit(closed, pts, [r.start for r in runs], runs)
    starts = [r.start for r in lines]
    ends = [r.end for r in lines]
    m = len(lines)
    if not closed:
        if starts[0] <= short_gap:
            starts[0] = 0
        if n - 1 - ends[-1] <= short_gap:
            ends[-1] = n - 1
    for i in range(m if closed else m - 1):
        j = (i + 1) % m
        gap = _span(n, ends[i], starts[j], closed)
        if gap <= short_gap:                      # a corner (possibly slightly rounded): the lines meet at one point
            c = (ends[i] + gap // 2) % n
            ends[i], starts[j] = c, c
    if not closed and starts[0] > 0:
        curve(0, starts[0])
    for i in range(m):
        runs.append(_Run(starts[i], ends[i], lines[i].line))
        if closed or i + 1 < m:
            nxt = starts[(i + 1) % m]
            if nxt != ends[i]:
                curve(ends[i], nxt)
    if not closed and ends[-1] < n - 1:
        curve(ends[-1], n - 1)
    corners = [r.start for r in runs] + ([] if closed else [n - 1])
    return _ChainFit(closed, pts, corners, runs)


def unify_angles(fits: list[_ChainFit], snap: bool) -> None:
    """Snap nearly horizontal/vertical lines (2 deg) and give lines within 1.5 deg of each other one common angle
    (length-weighted), across the whole picture. Changes the line directions in place."""
    lines = [r.line for f in fits for r in f.runs if r.line is not None and r.line.length > 0]
    if not lines or not snap:
        return
    ang = np.array([math.degrees(math.atan2(l.direction[1], l.direction[0])) % 180 for l in lines])
    wts = np.array([l.length for l in lines])
    target = ang.copy()
    for base in (0.0, 90.0, 180.0):
        target = np.where(np.abs(ang - base) <= 2.0, base % 180, target)
    rest = np.nonzero(np.all([np.abs(ang - b) > 2.0 for b in (0.0, 90.0, 180.0)], axis=0))[0]
    order = rest[np.argsort(ang[rest], kind='stable')]
    groups: list[list[int]] = []
    for i in order:
        if groups and ang[i] - ang[groups[-1][-1]] <= 1.5:
            groups[-1].append(int(i))
        else:
            groups.append([int(i)])
    for g in groups:
        target[g] = float(np.average(ang[g], weights=wts[g]))
    for l, t in zip(lines, target):
        d = np.array([math.cos(math.radians(t)), math.sin(math.radians(t))])
        l.direction = d if float(d @ l.direction) >= 0 else -d


def _intersect(a: _Line, b: _Line) -> np.ndarray | None:
    m = np.array([a.direction, -b.direction]).T
    if abs(float(np.linalg.det(m))) < 1e-6:
        return None
    s = np.linalg.solve(m, b.centre - a.centre)
    return a.centre + s[0] * a.direction


def _project(line: _Line, q: np.ndarray) -> np.ndarray:
    return line.centre + float((q - line.centre) @ line.direction) * line.direction


def emit(fit: _ChainFit, p: LogoParams, window: int) -> list[Segment]:
    pts = fit.pts
    if fit.closed and not fit.corners:                       # smooth closed curve (circle, blob)
        sm = _smooth_closed(pts, 1.0)
        half = len(sm) // 2
        loop = np.vstack([sm, sm[:1]])
        cub = fit_curve(loop[:half + 1], p.curve_tolerance) + fit_curve(loop[half:], p.curve_tolerance)
        return [Segment('C', [tuple(map(float, q)) for q in c]) for c in cub]
    runs = fit.runs
    m = len(runs)
    # vertices: where the runs meet (open chains keep their end points: they are shared junctions)
    verts: list[np.ndarray] = []
    for i, r in enumerate(runs):
        ci = r.start
        orig = pts[ci]
        if not fit.closed and i == 0:
            verts.append(orig)
            continue
        prev = runs[i - 1] if (fit.closed or i > 0) else None
        a = prev.line if prev else None
        b = r.line
        if p.pixel:
            verts.append(orig)
        elif a is not None and b is not None:
            x = _intersect(a, b)
            verts.append(x if x is not None and float(np.linalg.norm(x - orig)) <= 6 * window else orig)
        elif a is not None:
            verts.append(_project(a, orig))
        elif b is not None:
            verts.append(_project(b, orig))
        else:
            verts.append(orig)
    end_vertex = pts[runs[-1].end] if not fit.closed else verts[0]
    segs: list[Segment] = []
    for i, r in enumerate(runs):
        v0 = verts[i]
        v1 = verts[i + 1] if i + 1 < m else end_vertex
        if r.line is not None:
            segs.append(Segment('L', [tuple(map(float, v0)), tuple(map(float, v1))]))
            continue
        inner = _run_points(pts, r.start, r.end)[1:-1]
        poly = np.vstack([v0[None], inner, v1[None]]) if len(inner) else np.vstack([v0[None], v1[None]])
        cub = fit_curve(_smooth_open(poly, 1.0), p.curve_tolerance)
        segs.extend(Segment('C', [tuple(map(float, q)) for q in c]) for c in cub)
    if p.corner_radius > 0 and not p.pixel:
        segs = _round_corners(segs, p.corner_radius, fit.closed)
    return segs


def _round_corners(segs: list[Segment], radius: float, closed: bool) -> list[Segment]:
    """Replace the corner between two lines by a quadratic curve that starts and ends `radius` px from it."""
    if not segs:
        return segs
    out = [Segment(s.kind, list(s.points)) for s in segs]
    n = len(out)
    joins = range(n) if closed else range(1, n)
    cut: dict[int, tuple[Point, Point, Point]] = {}
    for j in joins:
        a, b = out[j - 1], out[j]
        if a.kind != 'L' or b.kind != 'L':
            continue
        corner = np.array(b.points[0])
        pa, pb = np.array(a.points[0]), np.array(b.points[-1])
        la, lb = float(np.linalg.norm(corner - pa)), float(np.linalg.norm(pb - corner))
        r = min(radius, 0.45 * la, 0.45 * lb)
        if r <= 0.01:
            continue
        s = corner + (pa - corner) / la * r
        e = corner + (pb - corner) / lb * r
        cut[j] = ((float(s[0]), float(s[1])), (float(corner[0]), float(corner[1])), (float(e[0]), float(e[1])))
    if not cut:
        return out
    result: list[Segment] = []
    for j, s in enumerate(out):
        start, end = s.points[0], s.points[-1]
        if j in cut:
            start = cut[j][2]
        nxt = (j + 1) % n
        if nxt in cut and (closed or nxt > 0):
            end = cut[nxt][0]
        if s.kind == 'L':
            result.append(Segment('L', [start, end]))
        else:
            result.append(s)
        if nxt in cut and (closed or nxt > 0):
            result.append(Segment('Q', [cut[nxt][0], cut[nxt][1], cut[nxt][2]]))
    return result


# --------------------------------------------------------------------------------------------- 9. serialize

def _fmt(v: float, decimals: int) -> str:
    return _num(round(v, decimals), decimals)


def path_data(loops: list[list[Segment]], decimals: int, shift: Point, scale: float) -> str:
    """Absolute or relative command per segment, whichever is shorter; H/V for axis-aligned lines."""
    q = 10 ** decimals
    out: list[str] = []

    def r(pt: Point) -> Point:
        return (round((pt[0] - shift[0]) / scale * q) / q, round((pt[1] - shift[1]) / scale * q) / q)

    def nums(vals: list[float]) -> str:
        s = ''
        prev = ''
        for v in vals:
            t = _fmt(v, decimals)
            if prev and not (t.startswith('-') or (t.startswith('.') and '.' in prev)):
                s += ' '
            s += t
            prev = t
        return s

    for loop in loops:
        if not loop:
            continue
        cur = r(loop[0].points[0])
        start = cur
        out.append('M' + nums([cur[0], cur[1]]))
        for k, s in enumerate(loop):
            pts = [r(pt) for pt in s.points[1:]]
            end = pts[-1]
            if s.kind == 'L':
                if k == len(loop) - 1 and end == start:
                    break                                # Z closes it
                if end[1] == cur[1] and end[0] != cur[0]:
                    cands = ['H' + nums([end[0]]), 'h' + nums([end[0] - cur[0]])]
                elif end[0] == cur[0] and end[1] != cur[1]:
                    cands = ['V' + nums([end[1]]), 'v' + nums([end[1] - cur[1]])]
                elif end == cur:
                    continue
                else:
                    cands = ['L' + nums([end[0], end[1]]), 'l' + nums([end[0] - cur[0], end[1] - cur[1]])]
            else:
                letter = s.kind
                cands = [letter + nums([v for pt in pts for v in pt]),
                         letter.lower() + nums([v for pt in pts for v in (pt[0] - cur[0], pt[1] - cur[1])])]
            out.append(min(cands, key=len))
            cur = end
        out.append('Z')
    return ''.join(out)


def _bbox(segs: list[Segment]) -> tuple[float, float, float, float]:
    xs: list[float] = []
    ys: list[float] = []
    for s in segs:
        pts = np.array(s.points)
        if s.kind == 'L':
            samp = pts
        else:
            t = np.linspace(0, 1, 17)[:, None]
            if s.kind == 'C':
                p0, p1, p2, p3 = pts
                samp = ((1 - t) ** 3) * p0 + 3 * ((1 - t) ** 2) * t * p1 + 3 * (1 - t) * t * t * p2 + t ** 3 * p3
            else:
                p0, p1, p2 = pts
                samp = ((1 - t) ** 2) * p0 + 2 * (1 - t) * t * p1 + t * t * p2
        xs.extend(samp[:, 0].tolist())
        ys.extend(samp[:, 1].tolist())
    return min(xs), min(ys), max(xs), max(ys)


def _esc(s: str) -> str:
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def vectorize_logo(image: Image.Image, p: LogoParams, *, max_colors: int | None = None,
                   palette: tuple[str, ...] | None = None, keep_background: bool = False, decimals: int = 2,
                   color_groups: bool = False, min_area: int = 16,
                   tone: Callable[[np.ndarray], np.ndarray] | None = None,
                   stage: Callable[[str, float], None] | None = None) -> LogoResult:
    report = stage or (lambda name, fraction: None)
    report('ink', 0.05)
    rgb, alpha, scale = load(image, 0 if p.pixel else 256)
    if tone is not None:
        rgb = tone(rgb)
    h, w = rgb.shape[:2]
    bg = background(rgb, alpha, p, keep_background)
    pal = quantize(rgb, ~bg.mask, p, max_colors, palette)
    k = len(pal.rgb)
    report('regions', 0.3)
    label = assign(rgb, bg, pal)
    if not p.pixel:
        label = majority(label, k + 1)
    content = int((label < k).sum())
    label = remove_specks(label, k + 1, max(min_area * scale * scale, int(p.min_area_ratio * content)))
    sh = shapes(label, k, p)
    report('curves', 0.6)
    chains, polys = contours(sh, rgb, pal, bg, p)
    window = 3 * scale if p.pixel else max(4, int(round(min(h, w) / 200)) * scale)
    fits = [analyse(c, poly, p, window) for c, poly in zip(chains, polys)]
    unify_angles(fits, p.snap_angles and not p.pixel)
    fitted = [emit(f, p, window) for f in fits]
    report('svg', 0.9)
    loops_by_shape = region_loops(chains)
    shape_loops: dict[int, list[list[Segment]]] = {}
    every: list[Segment] = []
    n_shapes = len(sh.color) - 1
    for s in range(1, n_shapes + 1):
        loops = []
        for loop in loops_by_shape.get(s, []):
            segs: list[Segment] = []
            for ci, rev in loop:
                part = fitted[ci]
                segs.extend([x.reversed() for x in reversed(part)] if rev else part)
            loops.append(segs)
            every.extend(segs)
        shape_loops[s] = loops
    if every and p.trim:
        x0, y0, x1, y1 = _bbox(every)
        pad = p.padding * scale
        eps = 1e-3                       # float noise must not add a pixel
        x0, y0 = max(0.0, math.floor(x0 - pad + eps)), max(0.0, math.floor(y0 - pad + eps))
        x1, y1 = min(float(w), math.ceil(x1 + pad - eps)), min(float(h), math.ceil(y1 + pad - eps))
    else:
        x0, y0, x1, y1 = 0.0, 0.0, float(w), float(h)
    vw, vh = (x1 - x0) / scale, (y1 - y0) / scale
    hexes = [to_hex(c) for c in pal.rgb]
    paths: dict[int, list[str]] = {}
    for order, s in enumerate(sh.order):
        d = path_data(shape_loops[s], decimals, (x0, y0), scale)
        if not d:
            continue
        ci = sh.color[s]
        rule = ' fill-rule="evenodd"' if len(shape_loops[s]) > 1 else ''
        paths.setdefault(ci, []).append(
            f'<path id="shape-{ci}-{order}" class="color-{ci}" fill="{hexes[ci]}"{rule} d="{d}"/>')
    if color_groups:
        body = ''.join(f'<g id="color-{ci}">{"".join(paths[ci])}</g>' for ci in sorted(paths))
    else:
        flat = sorted(((int(x.split('-')[2].split('"')[0]), x) for ci in paths for x in paths[ci]))
        body = ''.join(x for _, x in flat)
    title = f'<title>{_esc(p.title)}</title>' if p.title else ''
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_fmt(vw, 2)} {_fmt(vh, 2)}">{title}'
           f'<g id="{_esc(p.name)}">{body}</g></svg>\n')
    used = [hexes[c] for c in sorted(paths)]
    return LogoResult(svg, sum(len(v) for v in paths.values()), used,
                      (x0 / scale, y0 / scale, vw, vh), pal.warnings)
