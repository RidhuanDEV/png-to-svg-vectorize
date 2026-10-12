"""Region segmentation and gradient fitting for the fill layer.

Soft shading becomes ONE region with a gradient fill; hard color boundaries (lips, blush, different fabrics)
stay separate regions. Regions are merged with a union-find over the adjacency graph.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage

from .color import guided_filter, reduce_palette, to_lab
from .gradients import linear_model, ls_stops, radial_residuals


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
    same_de: float = 5.0        # thin (<= 2 px) or small (< 500 px) regions with practically the neighbour's color
                                #    merge into it even if their anti-aliased inside defeats the gradient test
    sliver_de: float = 6.0      # regions at most ~2 px wide whose color is a blend of two neighbours (anti-aliasing
                                #    between flat shapes) merge into the closer one if the blend residual is below this
    flat_de: float = 2.5        # gradients weaker than this become solid fills
    gradient_min_area: int = 300  # smaller regions are always solid (a gradient def costs ~200 bytes)
    radial_merge: bool = True   # grow blob-shaded regions (ball, blush, glow) over neighbours one radial gradient
    radial_rgb: float = 6.0     #    still explains: RMS render error (sRGB 0-255) of that radial gradient
    max_passes: int = 30


def _roots(parent: np.ndarray) -> np.ndarray:
    while True:
        nxt = parent[parent]
        if np.array_equal(nxt, parent):
            return parent
        parent = nxt


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


def _slivers(thin: np.ndarray, pairs: np.ndarray, mean: np.ndarray, max_de: float):
    """Find slivers: regions without an interior pixel (`thin`) whose mean color lies on the segment between two of
    their neighbours' colors (an anti-aliasing blend). Returns two bool arrays over `pairs`: the pair (sliver,
    closer neighbour) is marked on the sliver's side (column 0 or 1)."""
    side0, side1 = np.zeros(len(pairs), bool), np.zeros(len(pairs), bool)
    nb: dict[int, list[tuple[int, int]]] = {}
    cand = np.nonzero(thin[pairs[:, 0]] | thin[pairs[:, 1]])[0]
    for k, (a, b) in zip(cand.tolist(), pairs[cand].tolist()):
        if thin[a]:
            nb.setdefault(a, []).append((b, k))
        if thin[b]:
            nb.setdefault(b, []).append((a, k))
    for r, lst in nb.items():
        if len(lst) < 2:
            continue
        nbr = np.array(lst)                                   # (m, 2): neighbour label, pair index
        M = mean[nbr[:, 0]]                                   # neighbour colors
        D = M[None, :, :] - M[:, None, :]                     # D[x, y] = M[y] - M[x]
        t = ((mean[r] - M)[:, None, :] * D).sum(-1) / np.maximum((D * D).sum(-1), 1e-9)
        res = np.linalg.norm(mean[r] - (M[:, None, :] + t[..., None] * D), axis=-1)
        ok = (t > 0.05) & (t < 0.95) & (res < max_de) & np.triu(np.ones_like(t, bool), 1)
        if not ok.any():
            continue
        x, y = np.unravel_index(np.argmin(np.where(ok, res, np.inf)), res.shape)
        k = int(nbr[x, 1] if t[x, y] < 0.5 else nbr[y, 1])   # the closer of the two neighbours
        (side0 if pairs[k, 0] == r else side1)[k] = True
    return side0, side1


def segment(rgb: np.ndarray, near_outline: np.ndarray, p: RegionParams | None = None) -> np.ndarray:
    """Return an int32 label image (1..n)."""
    p = p or RegionParams()
    smooth = guided_filter(np.asarray(Image.fromarray(rgb).filter(ImageFilter.MedianFilter(5))))
    q = reduce_palette(smooth, merge_de=p.palette_de)
    key = (q[..., 0].astype(np.int64) << 16) | (q[..., 1].astype(np.int64) << 8) | q[..., 2]
    _, inv = np.unique(key, return_inverse=True)
    inv = inv.reshape(key.shape)
    if inv.max() < 256:          # majority vote in 5x5 on palette indices (one band, true color mode)
        inv = np.asarray(Image.fromarray(inv.astype(np.uint8)).filter(ImageFilter.ModeFilter(5))).astype(np.int64)
        _, inv = np.unique(inv, return_inverse=True)
        inv = inv.reshape(key.shape)
    else:                        # rare: too many colors for one 8-bit band, vote per channel
        q = np.asarray(Image.fromarray(q).filter(ImageFilter.ModeFilter(5)))
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
    h, w = label.shape
    yy, xx = np.indices((h, w))
    X = ((xx - w / 2) / 100.0).ravel()
    Y = ((yy - h / 2) / 100.0).ravel()
    flat = label.ravel()

    # Statistics are additive: compute them once per initial label, then every pass only aggregates n values
    # through the union-find instead of touching every pixel again.
    def bc(wts):
        return np.bincount(flat, weights=wts, minlength=n + 1)
    st0 = {'n': bc(None), 'sx': bc(X), 'sy': bc(Y), 'sxx': bc(X * X), 'sxy': bc(X * Y), 'syy': bc(Y * Y),
           'sv': np.stack([bc(lab[:, c]) for c in range(3)], 1),
           'svx': np.stack([bc(lab[:, c] * X) for c in range(3)], 1),
           'svy': np.stack([bc(lab[:, c] * Y) for c in range(3)], 1),
           'svv': np.stack([bc(lab[:, c] ** 2) for c in range(3)], 1)}
    ring0 = bc(near_outline.ravel().astype(np.float64))
    # pixel adjacencies across initial label boundaries (the only places where labels can differ)
    idx = np.arange(h * w).reshape(h, w)
    ea = np.concatenate([idx[:, :-1].ravel(), idx[:-1, :].ravel()])
    eb = np.concatenate([idx[:, 1:].ravel(), idx[1:, :].ravel()])
    keep = flat[ea] != flat[eb]
    ea, eb = ea[keep], eb[keep]
    la, lb = flat[ea], flat[eb]
    border = np.concatenate([idx[0], idx[-1], idx[:, 0], idx[:, -1]])              # never interior pixels

    def agg(root, v):
        if v.ndim == 1:
            return np.bincount(root, weights=v, minlength=n + 1)
        return np.stack([np.bincount(root, weights=v[:, c], minlength=n + 1) for c in range(v.shape[1])], 1)

    parent = np.arange(n + 1)
    for _ in range(p.max_passes):
        parent = _roots(parent)
        st = {k: agg(parent, v) for k, v in st0.items()}
        area = st['n']
        mean = st['sv'] / np.maximum(area, 1)[:, None]
        ring = agg(parent, ring0) / np.maximum(area, 1)
        ra, rb = parent[la], parent[lb]
        diff = ra != rb
        if not diff.any():
            break
        code = np.unique(np.minimum(ra[diff], rb[diff]) * np.int64(n + 1) + np.maximum(ra[diff], rb[diff]))
        pairs = np.stack([code // (n + 1), code % (n + 1)], 1)
        edge_px = np.zeros(h * w, bool)
        edge_px[ea[diff]] = True
        edge_px[eb[diff]] = True
        edge_px[border] = True
        edge2 = ndimage.binary_dilation(edge_px.reshape(h, w)).ravel()             # within 2 px of a boundary
        thin2 = np.bincount(parent[flat[edge2]], minlength=n + 1) >= area
        de = np.linalg.norm(mean[pairs[:, 0]] - mean[pairs[:, 1]], axis=1)
        # forced merges: a flagged region (tiny, small, rim along an outline, anti-aliasing sliver) JOINS its most
        # similar neighbour; flags[c] says which side of the pair is flagged
        flags = []
        for c, sl in zip((0, 1), _slivers(thin2, pairs, mean, p.sliver_de)):
            r = pairs[:, c]
            flags.append((area[r] < p.speckle) | ((area[r] < p.min_area) & (de < p.small_de))
                         | ((ring[r] >= p.ring_fraction) & (de < p.ring_de)) | sl
                         | ((thin2[r] | (area[r] < 500)) & (de < p.same_de)))
        forced = flags[0] | flags[1]
        soft = de < p.merge_de
        if soft.any():
            a, b = pairs[soft, 0], pairs[soft, 1]
            union = {k: st[k][a] + st[k][b] for k in st}
            extra = _sse(union) - _sse(st, a) - _sse(st, b)
            per_px = np.sqrt(np.maximum(extra, 0) / np.maximum(np.minimum(area[a], area[b]), 1))
            small_area = np.maximum(np.minimum(area[a], area[b]), 1)
            limit = p.fit_de * np.clip(np.sqrt(p.fit_area / small_area), 0.3, 1.0) if p.fit_area else p.fit_de
            ok = per_px < limit
            soft[np.nonzero(soft)[0]] = ok
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
    out = compact.reshape(label.shape).astype(np.int32) + 1
    return _grow_radial(out, smooth.astype(np.float64), lab.reshape(h, w, 3), p) if p.radial_merge else out


def _grow_radial(label: np.ndarray, rgb: np.ndarray, lab: np.ndarray, p: RegionParams) -> np.ndarray:
    """Concentric shading (a ball, a glow) is split into bands by the linear-gradient merge. Seeds are regions whose
    own shading is clearly radial; each absorbs neighbouring bands while ONE radial gradient - fitted and evaluated
    as the SVG renders it - keeps the RMS error below radial_rgb, both over the union and over the absorbed band
    itself (so small distinct details are never diluted into a big blob). Work stays inside local bounding boxes."""
    h, w = label.shape
    max_area = 0.3 * h * w                            # blobs, not backgrounds
    flat = label.ravel()
    n = int(label.max())
    area = np.bincount(flat, minlength=n + 1)
    mean = np.stack([np.bincount(flat, weights=lab[..., c].ravel(), minlength=n + 1) for c in range(3)], 1)
    mean /= np.maximum(area, 1)[:, None]
    objects = list(ndimage.find_objects(label))
    alive = np.ones(n + 1, bool)
    lim2 = p.radial_rgb ** 2
    for r in sorted(range(1, n + 1), key=lambda q: area[q]):
        if not (p.gradient_min_area <= area[r] <= max_area) or not alive[r] or objects[r - 1] is None:
            continue
        sl = objects[r - 1]
        ys, xs = _interior(label, sl, (r,))
        if len(ys) < 30:
            continue
        cols = rgb[ys, xs]
        lin = linear_model(ys + 0.5, xs + 0.5, cols)
        e_lin = np.sqrt(ls_stops(lin[0], cols)[1]) if lin is not None else np.inf
        if e_lin < 2.0:
            continue                                  # a linear gradient already explains it
        fit = radial_residuals(ys, xs, cols)
        if fit is None or np.sqrt(fit[0].mean()) > min(p.radial_rgb, 0.8 * e_lin):
            continue                                  # not a radial blob: leave it to the linear merge
        cur_area = int(area[r])
        model = fit[1]                                # current center/ellipse: the start for every union fit
        failed: set[int] = set()                      # bands that did not fit stay rejected for this seed
        budget = 48                                   # candidate fits per seed
        for _ in range(64):
            y0, y1 = max(sl[0].start - 1, 0), min(sl[0].stop + 1, h)
            x0, x1 = max(sl[1].start - 1, 0), min(sl[1].stop + 1, w)
            win = label[y0:y1, x0:x1]
            m = win == r
            ring = ndimage.binary_dilation(m) & ~m
            best = None
            for q in np.unique(win[ring]):
                if budget <= 0:
                    break
                if q == r or q in failed or not alive[q] or cur_area + area[q] > max_area:
                    continue
                if np.linalg.norm(mean[q] - mean[r]) > 3 * p.merge_de:
                    continue
                qs = objects[q - 1]
                usl = (slice(min(sl[0].start, qs[0].start), max(sl[0].stop, qs[0].stop)),
                       slice(min(sl[1].start, qs[1].start), max(sl[1].stop, qs[1].stop)))
                uy, ux = _interior(label, usl, (r, q))
                own = label[uy, ux] == q
                own_lim = lim2
                if own.sum() < 10:                    # thin band: judge all its pixels, blur-tolerant limit
                    qy, qx = np.nonzero(label[usl] == q)
                    uy = np.r_[uy[~own], qy + usl[0].start]
                    ux = np.r_[ux[~own], qx + usl[1].start]
                    own = label[uy, ux] == q
                    own_lim = 4 * lim2
                budget -= 1
                got = radial_residuals(uy, ux, rgb[uy, ux], model)
                if got is None or got[0][~own].mean() >= lim2 or got[0][own].mean() >= own_lim:
                    failed.add(int(q))
                    continue
                if best is None or got[0][~own].mean() < best[0]:
                    best = (got[0][~own].mean(), q, usl, got[1])
            if best is None:
                break
            _, q, sl, model = best
            sub = label[sl]
            sub[sub == q] = r
            alive[q] = False
            cur_area += int(area[q])
            area[r] = cur_area
            objects[r - 1] = sl
            mean[r] = lab[sl][sub == r].mean(axis=0)
    _, compact = np.unique(label, return_inverse=True)
    return compact.reshape(label.shape).astype(np.int32) + 1


def _interior(label: np.ndarray, sl: tuple, ids: tuple, margin: int = 2):
    """Pixels of the union of `ids` inside `sl` that are at least `margin` px away from any other region: the
    smoothing used for segmentation blends colors across region boundaries, so those pixels are not trusted."""
    h, w = label.shape
    y0, y1 = max(sl[0].start - margin, 0), min(sl[0].stop + margin, h)
    x0, x1 = max(sl[1].start - margin, 0), min(sl[1].stop + margin, w)
    m = np.isin(label[y0:y1, x0:x1], ids)
    inner = ndimage.binary_erosion(m, iterations=margin, border_value=1)
    ys, xs = np.nonzero(inner)
    return ys + y0, xs + x0


def refine_boundaries(label: np.ndarray, rgb: np.ndarray, hidden: np.ndarray | None, iterations: int = 2,
                      radius: int = 2) -> np.ndarray:
    """Undo boundary shifts caused by the smoothing filters used for segmentation (thin tips and corners erode).

    A boundary pixel moves to a neighbouring label when its own (unfiltered) color is mostly that label's color:
    projected on the line between the two labels' LOCAL mean colors (same-label pixels in a (2r+1)^2 window), it
    sits beyond 60 % toward the neighbour. Anti-aliased pixels in between stay; sub-pixel offsets handle them."""
    h, w = label.shape
    rgb = rgb.astype(np.float32)
    k = 2 * radius + 1
    for _ in range(iterations):
        P = np.pad(label, 1, mode='edge')
        nb = np.stack([P[:-2, 1:-1], P[2:, 1:-1], P[1:-1, :-2], P[1:-1, 2:]])
        diff = nb != label
        cand = diff.any(0)
        if hidden is not None:
            cand &= ~hidden
        ys, xs = np.nonzero(cand)
        if len(ys) == 0:
            break
        other = nb[np.argmax(diff[:, ys, xs], axis=0), ys, xs]          # first differing 4-neighbour
        own = label[ys, xs]
        Lp = np.pad(label, radius, mode='edge')
        Cp = np.pad(rgb, ((radius, radius), (radius, radius), (0, 0)), mode='edge')
        oy, ox = np.mgrid[0:k, 0:k]
        wy, wx = ys[:, None] + oy.ravel(), xs[:, None] + ox.ravel()
        Lw, Cw = Lp[wy, wx], Cp[wy, wx]                                  # (N, k*k), (N, k*k, 3)
        mo, mt = Lw == own[:, None], Lw == other[:, None]
        no, nt = mo.sum(1), mt.sum(1)
        A = (Cw * mo[..., None]).sum(1) / np.maximum(no, 1)[:, None]
        B = (Cw * mt[..., None]).sum(1) / np.maximum(nt, 1)[:, None]
        ab = A - B
        den = (ab * ab).sum(1)
        a = ((rgb[ys, xs] - B) * ab).sum(1) / np.maximum(den, 1e-9)       # 1 = own color, 0 = other color
        move = (a < 0.4) & (den >= 30.0 ** 2) & (no >= 3) & (nt >= 3)
        if not move.any():
            break
        label = label.copy()
        label[ys[move], xs[move]] = other[move]
    return label
