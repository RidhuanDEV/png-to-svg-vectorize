"""Polyline smoothing, corner detection and least-squares cubic Bezier fitting (Schneider, Graphics Gems 1990).

A fitted curve is a list of segments; each segment is a (4, 2) array [P0, C1, C2, P3]. Straight pieces are
returned as cubics with control points on the chord (they still compress well as relative coordinates).
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage

_MAX_REPARAM = 4


def _normalize(v: np.ndarray) -> np.ndarray:
    n = float(np.hypot(v[0], v[1]))
    return v / n if n > 1e-12 else np.array([1.0, 0.0])


def _basis(t: np.ndarray) -> np.ndarray:
    """Cubic Bernstein basis, (N, 4)."""
    mt = 1 - t
    return np.stack([mt * mt * mt, 3 * mt * mt * t, 3 * mt * t * t, t * t * t], 1)


def _bezier(ctrl: np.ndarray, t: np.ndarray) -> np.ndarray:
    return _basis(t) @ ctrl


_D1 = np.array([[-1, 1, 0, 0], [0, -1, 1, 0], [0, 0, -1, 1]], np.float64) * 3     # control points -> 1st derivative
_D2 = np.array([[1, -2, 1, 0], [0, 1, -2, 1]], np.float64) * 6                    # control points -> 2nd derivative


def _bezier_d1(ctrl: np.ndarray, t: np.ndarray) -> np.ndarray:
    mt = 1 - t
    return np.stack([mt * mt, 2 * mt * t, t * t], 1) @ (_D1 @ ctrl)


def _bezier_d2(ctrl: np.ndarray, t: np.ndarray) -> np.ndarray:
    return np.stack([1 - t, t], 1) @ (_D2 @ ctrl)


def _chord_params(p: np.ndarray) -> np.ndarray:
    dp = np.diff(p, axis=0)
    d = np.r_[0.0, np.cumsum(np.hypot(dp[:, 0], dp[:, 1]))]
    return d / d[-1] if d[-1] > 0 else np.linspace(0, 1, len(p))


def _generate(p: np.ndarray, u: np.ndarray, t1: np.ndarray, t2: np.ndarray) -> np.ndarray:
    first, last = p[0], p[-1]
    B = _basis(u)
    a1 = np.outer(B[:, 1], t1)
    a2 = np.outer(B[:, 2], t2)
    c00, c01, c11 = (a1 * a1).sum(), (a1 * a2).sum(), (a2 * a2).sum()
    tmp = p - np.outer(B[:, 0] + B[:, 1], first) - np.outer(B[:, 2] + B[:, 3], last)
    x0, x1 = (a1 * tmp).sum(), (a2 * tmp).sum()
    det = c00 * c11 - c01 * c01
    seg = float(np.hypot(*(last - first)))
    if abs(det) > 1e-12:
        al, ar = (x0 * c11 - x1 * c01) / det, (c00 * x1 - c01 * x0) / det
    else:
        al = ar = seg / 3
    eps = 1e-6 * seg
    if al < eps or ar < eps or al > 2 * seg or ar > 2 * seg:
        al = ar = seg / 3              # Wu/Barsky heuristic fallback
    return np.array([first, first + t1 * al, last + t2 * ar, last])


def _reparam(ctrl: np.ndarray, p: np.ndarray, u: np.ndarray) -> np.ndarray:
    q, q1, q2 = _bezier(ctrl, u), _bezier_d1(ctrl, u), _bezier_d2(ctrl, u)
    num = ((q - p) * q1).sum(axis=1)
    den = (q1 * q1).sum(axis=1) + ((q - p) * q2).sum(axis=1)
    with np.errstate(divide='ignore', invalid='ignore'):
        step = np.where(np.abs(den) > 1e-12, num / den, 0.0)
    return np.clip(u - step, 0.0, 1.0)


def _max_error(ctrl: np.ndarray, p: np.ndarray, u: np.ndarray, err2: np.ndarray):
    """Largest squared deviation relative to the per-point tolerance (< 1 = within tolerance)."""
    d = np.sum((_bezier(ctrl, u) - p) ** 2, axis=1) / err2
    i = int(np.argmax(d))
    return float(d[i]), i


def _fit(p: np.ndarray, t1: np.ndarray, t2: np.ndarray, err2: np.ndarray, out: list, depth: int = 0) -> None:
    n = len(p)
    if n == 2 or depth > 24:
        dist = float(np.hypot(*(p[-1] - p[0]))) / 3
        out.append(np.array([p[0], p[0] + t1 * dist, p[-1] + t2 * dist, p[-1]]))
        return
    u = _chord_params(p)
    ctrl = _generate(p, u, t1, t2)
    e, split = _max_error(ctrl, p, u, err2)
    if e < 1:
        out.append(ctrl)
        return
    if e < 16:
        for _ in range(_MAX_REPARAM):
            u = _reparam(ctrl, p, u)
            ctrl = _generate(p, u, t1, t2)
            e, split = _max_error(ctrl, p, u, err2)
            if e < 1:
                out.append(ctrl)
                return
    split = min(max(split, 1), n - 2)
    tc = _normalize(p[split - 1] - p[split + 1])
    _fit(p[:split + 1], t1, tc, err2[:split + 1], out, depth + 1)
    _fit(p[split:], -tc, t2, err2[split:], out, depth + 1)


def fit_curve(p: np.ndarray, error) -> list[np.ndarray]:
    """Fit cubic Beziers to an open polyline (N, 2) with max deviation `error` (scalar or one value per point)."""
    if len(p) < 2:
        return []
    k = min(3, len(p) - 1)
    t1 = _normalize(p[k] - p[0])
    t2 = _normalize(p[-1 - k] - p[-1])
    out: list[np.ndarray] = []
    err = np.broadcast_to(np.asarray(error, np.float64), (len(p),))
    _fit(p, t1, t2, err * err, out)
    return out


def _midpoints(corners: np.ndarray, closed: bool, offsets: np.ndarray | None = None) -> np.ndarray:
    """Crack corners -> crack midpoints (removes the pixel staircase), each optionally moved by its sub-pixel
    offset toward the right side of the traversal. Open chains keep their exact end corners (junctions are shared
    by several chains)."""
    nxt = np.roll(corners, -1, axis=0) if closed else corners[1:]
    cur = corners if closed else corners[:-1]
    mid = (cur + nxt) / 2
    if offsets is not None:
        d = nxt - cur
        mid = mid - offsets[:, None] * np.stack([d[:, 1], -d[:, 0]], 1)     # minus left normal = toward the right
    if closed:
        return mid
    return np.vstack([corners[:1], mid, corners[-1:]]).astype(np.float64)


def _smooth_closed(p: np.ndarray, sigma: float) -> np.ndarray:
    if sigma <= 0 or len(p) < 5:
        return p
    return ndimage.gaussian_filter1d(p, sigma, axis=0, mode='wrap')


def _smooth_open(p: np.ndarray, sigma: float) -> np.ndarray:
    """Gaussian smoothing along an open polyline; end points stay exactly where they are and the smoothing
    fades in over ~2 sigma so the curve still leaves the ends in their own direction."""
    n = len(p)
    if sigma <= 0 or n < 5:
        return p
    sm = ndimage.gaussian_filter1d(p, sigma, axis=0, mode='nearest')
    idx = np.arange(n)
    w = np.clip(np.minimum(idx, n - 1 - idx) / max(2 * sigma, 1), 0, 1)[:, None]
    out = p * (1 - w) + sm * w
    out[0], out[-1] = p[0], p[-1]
    return out


def corner_indices(p: np.ndarray, closed: bool, window: int = 4, min_turn_deg: float = 55.0) -> list[int]:
    """Indices where the polyline turns sharply (measured over +-window points), non-maximum suppressed."""
    n = len(p)
    if n < 2 * window + 3:
        return []
    if closed:
        a = np.roll(p, window, axis=0)
        b = np.roll(p, -window, axis=0)
        idx = np.arange(n)
    else:
        idx = np.arange(window, n - window)
        a, b = p[idx - window], p[idx + window]
        p = p[idx]
    v1 = _unit_rows(p - a)
    v2 = _unit_rows(b - p)
    turn = np.degrees(np.arccos(np.clip((v1 * v2).sum(axis=1), -1, 1)))
    cand = np.nonzero(turn > min_turn_deg)[0]
    picked: list[int] = []
    for c in cand[np.argsort(-turn[cand])]:
        if all(abs(int(idx[c]) - q) > window for q in picked):
            picked.append(int(idx[c]))
    return sorted(picked)


def _unit_rows(v: np.ndarray) -> np.ndarray:
    n = np.hypot(v[:, 0], v[:, 1])[:, None]
    return v / np.where(n > 1e-12, n, 1)


def fit_chain(corners: np.ndarray, closed: bool, sigma: float, error, window: int = 4,
              corner_deg: float = 55.0, offsets: np.ndarray | None = None) -> list[np.ndarray]:
    """Crack-edge chain -> smooth cubic Bezier segments. Sharp corners (turn > corner_deg over +-window points of
    the smoothed curve) are kept: the chain is split there and each piece is smoothed with pinned ends.
    `error` is the allowed deviation: a scalar, or one value per corner (e.g. looser where the boundary is hidden).
    `offsets` (one per crack) move the boundary to its sub-pixel position (see planar.subpixel_offsets)."""
    raw = _midpoints(corners, closed, offsets)
    tol = np.broadcast_to(np.asarray(error, np.float64), (len(corners),))
    tol = np.minimum(tol, np.roll(tol, -1)) if closed else np.r_[tol[:1], np.minimum(tol[:-1], tol[1:]), tol[-1:]]
    if closed:
        cs = corner_indices(_smooth_closed(raw, sigma), True, window, corner_deg)
        if not cs:
            p = _smooth_closed(raw, sigma)
            half = len(p) // 2
            loop, lt = np.vstack([p, p[:1]]), np.r_[tol, tol[:1]]
            return fit_curve(loop[:half + 1], lt[:half + 1]) + fit_curve(loop[half:], lt[half:])
        start = cs[0]
        raw = np.vstack([raw[start:], raw[:start + 1]])
        tol = np.r_[tol[start:], tol[:start + 1]]
        cs = [c - start for c in cs] + [len(raw) - 1]
    else:
        cs = [0] + corner_indices(_smooth_open(raw, sigma), False, window, corner_deg) + [len(raw) - 1]
    segs: list[np.ndarray] = []
    for a, b in zip(cs[:-1], cs[1:]):
        if b > a:
            segs += fit_curve(_smooth_open(raw[a:b + 1], sigma), tol[a:b + 1])
    return segs
