"""Region segmentation and gradient fitting for the fill layer.

Soft shading becomes ONE region with a gradient fill; hard color boundaries (lips, blush, different fabrics)
stay separate regions. Regions are merged with a union-find over the adjacency graph.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage

from .color import guided_filter, reduce_palette, to_hex, to_lab


@dataclass
class RegionParams:
    palette_de: float = 3.0     # initial fine palette
    merge_de: float = 9.0       # neighbours with mean colors closer than this may merge (soft gradients)...
    fit_de: float = 3.5         # ...only if ONE linear gradient still explains the union: extra fit error per pixel
                                #    of the smaller region (Delta E) must stay below this (keeps rings, blush, shapes)
    min_area: int = 40          # regions smaller than this (px) merge into the most similar neighbour...
    small_de: float = 22.0      # ...if not too different (keeps nose tips, mouth interiors)
    ring_de: float = 20.0       # thin rims hugging outlines (sharpening halos) merge if closer than this
    ring_fraction: float = 0.7  # ...and at least this fraction of their pixels lie within ring_dist of an outline
    ring_dist: int = 3
    flat_de: float = 2.5        # gradients weaker than this become solid fills
    gradient_min_area: int = 300  # smaller regions are always solid (a gradient def costs ~200 bytes)
    max_passes: int = 30


def _roots(parent: np.ndarray) -> np.ndarray:
    while True:
        nxt = parent[parent]
        if np.array_equal(nxt, parent):
            return parent
        parent = nxt


def _neighbour_pairs(label: np.ndarray) -> np.ndarray:
    a = np.concatenate([label[:, :-1].ravel(), label[:-1, :].ravel()])
    b = np.concatenate([label[:, 1:].ravel(), label[1:, :].ravel()])
    diff = a != b
    pairs = np.stack([np.minimum(a[diff], b[diff]), np.maximum(a[diff], b[diff])], axis=1)
    return np.unique(pairs, axis=0)


def _sse(st: dict, idx=None) -> np.ndarray:
    """Residual sum of squares of a per-region linear color model c = a + b*x + d*y (Lab, 3 channels),
    computed from sufficient statistics so unions can be evaluated without touching pixels."""
    g = (lambda k: st[k]) if idx is None else (lambda k: st[k][idx])
    n, sx, sy, sxx, sxy, syy = g('n'), g('sx'), g('sy'), g('sxx'), g('sxy'), g('syy')
    ridge = 1e-3 * (n + 1)
    M = np.stack([np.stack([n + 1e-9, sx, sy], -1), np.stack([sx, sxx + ridge, sxy], -1),
                  np.stack([sy, sxy, syy + ridge], -1)], -2)
    B = np.stack([g('sv'), g('svx'), g('svy')], -2)            # (k, 3 features, 3 channels)
    sol = np.linalg.solve(M, B)
    return np.maximum(g('svv').sum(-1) - (B * sol).sum((-1, -2)), 0.0)


def segment(rgb: np.ndarray, near_outline: np.ndarray, p: RegionParams | None = None) -> np.ndarray:
    """Return an int32 label image (1..n)."""
    p = p or RegionParams()
    smooth = guided_filter(np.asarray(Image.fromarray(rgb).filter(ImageFilter.MedianFilter(5))))
    q = np.asarray(Image.fromarray(reduce_palette(smooth, merge_de=p.palette_de)).filter(ImageFilter.ModeFilter(5)))
    key = (q[..., 0].astype(np.int64) << 16) | (q[..., 1].astype(np.int64) << 8) | q[..., 2]
    label = np.zeros(key.shape, np.int32)
    n = 0
    for k in np.unique(key):
        lab_k, c = ndimage.label(key == k)
        sel = lab_k > 0
        label[sel] = lab_k[sel] + n
        n += c

    lab = to_lab(smooth).reshape(-1, 3).astype(np.float64)
    near = near_outline.ravel().astype(np.float64)
    h, w = label.shape
    yy, xx = np.indices((h, w))
    X = ((xx - w / 2) / 100.0).ravel()
    Y = ((yy - h / 2) / 100.0).ravel()
    parent = np.arange(n + 1)
    flat = label.ravel()
    for _ in range(p.max_passes):
        parent = _roots(parent)
        cur = parent[flat]
        area = np.bincount(cur, minlength=n + 1).astype(np.float64)
        mean = np.stack([np.bincount(cur, weights=lab[:, c], minlength=n + 1) for c in range(3)], 1) / np.maximum(area, 1)[:, None]
        ring = np.bincount(cur, weights=near, minlength=n + 1) / np.maximum(area, 1)
        bc = lambda wts: np.bincount(cur, weights=wts, minlength=n + 1)
        st = {'n': area, 'sx': bc(X), 'sy': bc(Y), 'sxx': bc(X * X), 'sxy': bc(X * Y), 'syy': bc(Y * Y),
              'sv': np.stack([bc(lab[:, c]) for c in range(3)], 1),
              'svx': np.stack([bc(lab[:, c] * X) for c in range(3)], 1),
              'svy': np.stack([bc(lab[:, c] * Y) for c in range(3)], 1),
              'svv': np.stack([bc(lab[:, c] ** 2) for c in range(3)], 1)}
        pairs = _neighbour_pairs(cur.reshape(label.shape))
        if len(pairs) == 0:
            break
        de = np.linalg.norm(mean[pairs[:, 0]] - mean[pairs[:, 1]], axis=1)
        small = ((area[pairs[:, 0]] < p.min_area) | (area[pairs[:, 1]] < p.min_area)) & (de < p.small_de)
        rim = ((ring[pairs[:, 0]] >= p.ring_fraction) | (ring[pairs[:, 1]] >= p.ring_fraction)) & (de < p.ring_de)
        forced = small | rim
        soft = de < p.merge_de
        if soft.any():
            a, b = pairs[soft, 0], pairs[soft, 1]
            union = {k: st[k][a] + st[k][b] for k in st}
            extra = _sse(union) - _sse(st, a) - _sse(st, b)
            per_px = np.sqrt(np.maximum(extra, 0) / np.maximum(np.minimum(area[a], area[b]), 1))
            soft[np.nonzero(soft)[0]] = per_px < p.fit_de
        candidate = soft | forced
        if not candidate.any():
            break
        order = np.argsort(np.where(forced, de - 1000.0, de))
        touched: set[int] = set()
        merged = 0
        for k in order:
            if not candidate[k]:
                continue
            i, j = (int(v) for v in pairs[k])
            if i in touched or j in touched:
                continue
            parent[j] = i
            touched.update((i, j))
            merged += 1
        if merged == 0:
            break
    parent = _roots(parent)
    _, compact = np.unique(parent[label], return_inverse=True)
    return compact.reshape(label.shape).astype(np.int32) + 1


def fit_fill(ys: np.ndarray, xs: np.ndarray, colors: np.ndarray, gid: str, flat_de: float, min_area: int = 300):
    """Fit a 3-stop linear gradient along the direction of strongest color change.
    Returns (fill attribute value, <linearGradient> markup or '') in source-pixel coordinates."""
    mean = colors.mean(axis=0)
    if len(colors) < max(min_area, 30):
        return to_hex(mean), ''
    A = np.stack([np.ones_like(xs), xs, ys], axis=1).astype(np.float64)
    coef, *_ = np.linalg.lstsq(A, colors.astype(np.float64), rcond=None)
    _, _, vt = np.linalg.svd(coef[1:3].T)
    d = vt[0]
    t = xs * d[0] + ys * d[1]
    t0, t1 = np.percentile(t, [3, 97])
    if t1 - t0 < 4:
        return to_hex(mean), ''
    band = np.clip(((t - t0) / (t1 - t0) * 3).astype(int), 0, 2)
    stops = [colors[band == k].mean(axis=0) if (band == k).any() else mean for k in range(3)]
    lab = to_lab(np.array(stops, dtype=np.float32))
    if np.linalg.norm(lab[0] - lab[2]) < flat_de and np.linalg.norm(lab[0] - lab[1]) < flat_de:
        return to_hex(mean), ''
    cx, cy = xs.mean(), ys.mean()
    tc = cx * d[0] + cy * d[1]
    x1, y1 = cx + (t0 - tc) * d[0], cy + (t0 - tc) * d[1]
    x2, y2 = cx + (t1 - tc) * d[0], cy + (t1 - tc) * d[1]
    grad = (f'<linearGradient id="{gid}" gradientUnits="userSpaceOnUse" x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" '
            f'y2="{y2:.1f}"><stop offset=".17" stop-color="{to_hex(stops[0])}"/><stop offset=".5" '
            f'stop-color="{to_hex(stops[1])}"/><stop offset=".83" stop-color="{to_hex(stops[2])}"/></linearGradient>')
    return f'url(#{gid})', grad
