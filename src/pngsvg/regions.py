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
    fit_area: int = 5000        # above this size (px, smaller region) the allowed extra error shrinks ~1/sqrt(area),
                                #    down to 30 %: big flat areas split by objects keep their own gradients
    speckle: int = 10           # regions smaller than this (px) always merge into the most similar neighbour
    min_area: int = 40          # regions smaller than this (px) merge into the most similar neighbour...
    small_de: float = 22.0      # ...if not too different (keeps nose tips, mouth interiors)
    ring_de: float = 20.0       # thin rims hugging outlines (sharpening halos) merge if closer than this
    ring_fraction: float = 0.7  # ...and at least this fraction of their pixels lie within ring_dist of an outline
    ring_dist: int = 3
    sliver_de: float = 6.0      # regions at most ~2 px wide whose color is a blend of two neighbours (anti-aliasing
                                #    between flat shapes) merge into the closer one if the blend residual is below this
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


def _slivers(cur: np.ndarray, pairs: np.ndarray, mean: np.ndarray, n: int, max_de: float):
    """Find slivers: regions without an interior pixel whose mean color lies on the segment between two of their
    neighbours' colors (an anti-aliasing blend). Returns two bool arrays over `pairs`: the pair (sliver, closer
    neighbour) is marked on the sliver's side (column 0 or 1)."""
    inner = np.zeros_like(cur, bool)
    c = cur[1:-1, 1:-1]
    inner[1:-1, 1:-1] = (c == cur[:-2, 1:-1]) & (c == cur[2:, 1:-1]) & (c == cur[1:-1, :-2]) & (c == cur[1:-1, 2:])
    thin = np.bincount(cur[inner], minlength=n + 1) == 0
    side0, side1 = np.zeros(len(pairs), bool), np.zeros(len(pairs), bool)
    nb: dict[int, list[tuple[int, int]]] = {}
    for k, (a, b) in enumerate(pairs.tolist()):
        if thin[a]:
            nb.setdefault(a, []).append((b, k))
        if thin[b]:
            nb.setdefault(b, []).append((a, k))
    for r, lst in nb.items():
        if len(lst) < 2:
            continue
        m = mean[r]
        best = None
        for x in range(len(lst)):
            for y in range(x + 1, len(lst)):
                (j, kj), (i, ki) = lst[x], lst[y]
                d = mean[i] - mean[j]
                t = float(np.dot(m - mean[j], d) / max(np.dot(d, d), 1e-9))
                if not 0.05 < t < 0.95:
                    continue
                res = float(np.linalg.norm(m - (mean[j] + t * d)))
                if res < max_de and (best is None or res < best[0]):
                    best = (res, kj if t < 0.5 else ki)
        if best:
            (side0 if pairs[best[1], 0] == r else side1)[best[1]] = True
    return side0, side1


def segment(rgb: np.ndarray, near_outline: np.ndarray, p: RegionParams | None = None) -> np.ndarray:
    """Return an int32 label image (1..n)."""
    p = p or RegionParams()
    smooth = guided_filter(np.asarray(Image.fromarray(rgb).filter(ImageFilter.MedianFilter(5))))
    q = np.asarray(Image.fromarray(reduce_palette(smooth, merge_de=p.palette_de)).filter(ImageFilter.ModeFilter(5)))
    key = (q[..., 0].astype(np.int64) << 16) | (q[..., 1].astype(np.int64) << 8) | q[..., 2]
    _, inv = np.unique(key, return_inverse=True)
    inv = inv.reshape(key.shape)
    label = np.zeros(key.shape, np.int32)
    n = 0
    for k, sl in enumerate(ndimage.find_objects(inv + 1)):      # connected components per color, in its bbox
        lab_k, c = ndimage.label(inv[sl] == k)
        sel = lab_k > 0
        label[sl][sel] = lab_k[sel] + n
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
        # forced merges: a flagged region (tiny, small, rim along an outline, anti-aliasing sliver) JOINS its most
        # similar neighbour; flags[c] says which side of the pair is flagged
        flags = []
        for c, sl in zip((0, 1), _slivers(cur.reshape(label.shape), pairs, mean, n, p.sliver_de)):
            r = pairs[:, c]
            flags.append((area[r] < p.speckle) | ((area[r] < p.min_area) & (de < p.small_de))
                         | ((ring[r] >= p.ring_fraction) & (de < p.ring_de)) | sl)
        forced = flags[0] | flags[1]
        soft = de < p.merge_de
        if soft.any():
            a, b = pairs[soft, 0], pairs[soft, 1]
            union = {k: st[k][a] + st[k][b] for k in st}
            extra = _sse(union) - _sse(st, a) - _sse(st, b)
            per_px = np.sqrt(np.maximum(extra, 0) / np.maximum(np.minimum(area[a], area[b]), 1))
            small_area = np.maximum(np.minimum(area[a], area[b]), 1)
            limit = p.fit_de * np.clip(np.sqrt(p.fit_area / small_area), 0.3, 1.0) if p.fit_area else p.fit_de
            soft[np.nonzero(soft)[0]] = per_px < limit
        candidate = soft | forced
        if not candidate.any():
            break
        order = np.argsort(np.where(forced, de - 1000.0, de))
        absorbed: set[int] = set()   # merged away this pass
        busy: set[int] = set()       # absorbed something this pass
        merged = 0
        for k in order:
            if not candidate[k]:
                continue
            i, j = (int(v) for v in pairs[k])
            if forced[k] and flags[0][k] != flags[1][k]:
                if flags[0][k]:
                    i, j = j, i      # j = the flagged region, it joins i
            elif area[i] < area[j]:
                i, j = j, i          # otherwise the smaller region j joins i
            if i in absorbed or j in absorbed or j in busy:
                continue
            if not forced[k] and i in busy:
                continue             # soft merges use stale statistics: at most one per region per pass
            parent[j] = i
            absorbed.add(j)
            busy.add(i)
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
