"""Centerline tracing: line art (drawings, handwriting, technical lines) -> one stroked path along the middle of each
line, instead of filled outlines. For plotters, laser engraving, embroidery and editing line drawings.

dark ink mask -> Zhang-Suen thinning (one-pixel skeleton) -> graph of skeleton segments between end points and
junctions (short spurs pruned) -> smooth cubic Beziers; each path is stroked with the median ink width along it.
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage

from .color import to_hex
from .curves import _smooth_closed, _smooth_open, fit_curve

_OFFS = ((-1, -1), (-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1))


def ink_mask(gray: np.ndarray, threshold: int, min_area: int) -> np.ndarray:
    """Pixels darker than `threshold` (or lighter, when the picture is light lines on a dark background), lightly
    cleaned: pinholes closed, specks smaller than `min_area` removed."""
    h, w = gray.shape
    border = np.concatenate([gray[0], gray[-1], gray[:, 0], gray[:, -1]])
    mask = gray > threshold if np.median(border) < threshold else gray < threshold
    mask = ndimage.binary_closing(mask, iterations=1) | mask
    if min_area > 0:
        lab, n = ndimage.label(mask, structure=np.ones((3, 3)))
        if n:
            sizes = np.bincount(lab.ravel())
            keep = sizes >= min_area
            keep[0] = False
            mask = keep[lab]
    return mask


def thin(mask: np.ndarray) -> np.ndarray:
    """Zhang-Suen thinning, vectorized: a one-pixel wide, 8-connected skeleton of the mask."""
    img = np.pad(mask.astype(np.uint8), 1)
    while True:
        changed = False
        for step in (0, 1):
            c = img[1:-1, 1:-1]
            p2, p3, p4 = img[:-2, 1:-1], img[:-2, 2:], img[1:-1, 2:]
            p5, p6, p7 = img[2:, 2:], img[2:, 1:-1], img[2:, :-2]
            p8, p9 = img[1:-1, :-2], img[:-2, :-2]
            ring = (p2, p3, p4, p5, p6, p7, p8, p9, p2)
            b = p2 + p3 + p4 + p5 + p6 + p7 + p8 + p9
            a = sum(((ring[i] == 0) & (ring[i + 1] == 1)).astype(np.uint8) for i in range(8))
            if step == 0:
                cond = (p2 * p4 * p6 == 0) & (p4 * p6 * p8 == 0)
            else:
                cond = (p2 * p4 * p8 == 0) & (p2 * p6 * p8 == 0)
            remove = (c == 1) & (b >= 2) & (b <= 6) & (a == 1) & cond
            if remove.any():
                c[remove] = 0
                changed = True
        if not changed:
            return img[1:-1, 1:-1].astype(bool)


def trace(skel: np.ndarray, spur: float) -> list[tuple[np.ndarray, bool]]:
    """Skeleton -> polylines (pixel centres, x/y) between end points / junctions, plus closed loops. Branches that end
    in a free end and are shorter than `spur` px (noise from thinning thick lines) are dropped."""
    h, w = skel.shape
    ys, xs = np.nonzero(skel)
    ids = -np.ones((h + 2, w + 2), np.int64)
    ids[ys + 1, xs + 1] = np.arange(len(ys))
    nbrs: list[list[int]] = [[] for _ in range(len(ys))]
    for dy, dx in _OFFS:
        other = ids[ys + 1 + dy, xs + 1 + dx]
        ok = other >= 0
        if dy and dx:      # a diagonal step only where no orthogonal path exists (else every corner is a junction)
            ok &= (ids[ys + 1 + dy, xs + 1] < 0) & (ids[ys + 1, xs + 1 + dx] < 0)
        for i in np.nonzero(ok)[0]:
            nbrs[i].append(int(other[i]))
    deg = np.array([len(n) for n in nbrs])
    used: set[tuple[int, int]] = set()
    paths: list[tuple[list[int], bool]] = []

    def walk(start: int, nxt: int) -> list[int]:
        path, prev, cur = [start, nxt], start, nxt
        used.add((min(start, nxt), max(start, nxt)))
        while deg[cur] == 2:
            step = next((n for n in nbrs[cur] if n != prev and (min(cur, n), max(cur, n)) not in used), None)
            if step is None:
                break
            used.add((min(cur, step), max(cur, step)))
            path.append(step)
            prev, cur = cur, step
            if cur == start:
                break
        return path

    for node in np.nonzero(deg != 2)[0]:
        for n in nbrs[node]:
            if (min(node, n), max(node, n)) not in used:
                paths.append((walk(int(node), n), False))
    seen = np.zeros(len(ys), bool)
    for p, _ in paths:
        seen[p] = True
    for i in np.nonzero(~seen & (deg == 2))[0]:          # loops without any end point or junction
        if seen[i]:
            continue
        loop = walk(int(i), nbrs[i][0])
        seen[loop] = True
        paths.append((loop, True))

    out = []
    for p, closed in paths:
        one_free_end = (deg[p[0]] == 1) != (deg[p[-1]] == 1)      # a branch off a junction
        if not closed and one_free_end and len(p) < spur:
            continue
        pts = np.stack([xs[p], ys[p]], 1).astype(np.float64) + 0.5
        out.append((pts, closed))
    return out


def _path(pts: np.ndarray, closed: bool, sigma: float, tol: float) -> str:
    if closed and len(pts) > 8:
        p = _smooth_closed(pts[:-1] if np.allclose(pts[0], pts[-1]) else pts, sigma)
        half = len(p) // 2
        loop = np.vstack([p, p[:1]])
        segs = fit_curve(loop[:half + 1], tol) + fit_curve(loop[half:], tol)
    else:
        segs = fit_curve(_smooth_open(pts, sigma), tol)
    if not segs:
        return ''
    x0, y0 = segs[0][0]
    d = f'M{x0:.3f} {y0:.3f}' + ''.join(f'C{a[0]:.3f} {a[1]:.3f} {b[0]:.3f} {b[1]:.3f} {c[0]:.3f} {c[1]:.3f}'
                                        for _, a, b, c in segs)
    return d + ('Z' if closed else '')


def centerline(rgb: np.ndarray, threshold: int, min_area: int, smooth: float, tolerance: float, ink: str | None = None):
    """(paths as (absolute path data, stroke width), ink color) for an RGB picture."""
    gray = rgb.astype(np.float32) @ np.array([0.299, 0.587, 0.114], np.float32)
    mask = ink_mask(gray, threshold, min_area)
    if not mask.any():
        return [], ink or '#000000'
    depth = ndimage.distance_transform_edt(mask)
    skel = thin(mask)
    width = 2 * float(np.median(depth[skel])) if skel.any() else 1.0
    color = ink or to_hex(np.median(rgb[mask], axis=0))
    paths = []
    for pts, closed in trace(skel, spur=max(3.0, 1.5 * width)):
        d = _path(pts, closed, smooth, tolerance)
        if d:
            # the distance transform counts to the next background pixel centre: a w px line has ~(w + 1) / 2 at its
            # middle; the 75th percentile because the skeleton of a slanted line is not always on the exact middle
            sw = 2 * float(np.percentile(depth[pts[:, 1].astype(int), pts[:, 0].astype(int)], 75)) - 1
            paths.append((d, max(0.5, round(sw * 2) / 2)))
    return paths, color
