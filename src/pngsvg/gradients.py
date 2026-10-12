"""Gradient fills: a linear or elliptical radial gradient with three stops (offsets 0, .5, 1) per region.

Stop colors are solved by least squares against exactly what a renderer draws (piecewise linear interpolation in
sRGB between the stops, padded outside), so a straight color ramp is reproduced almost exactly.
"""
from __future__ import annotations

import numpy as np
from scipy import optimize

from .color import to_hex, to_lab

_SAMPLE = 2500          # pixels used for the non-linear center/shape fit
GAIN = 0.9              # a gradient must cut the solid-fill error to this fraction (else: solid)


def _hat(t: np.ndarray) -> np.ndarray:
    """Interpolation weights of the stops at offsets 0, .5, 1 for coordinates t in [0, 1], (N, 3)."""
    b0 = np.clip(1 - 2 * t, 0, 1)
    b2 = np.clip(2 * t - 1, 0, 1)
    return np.stack([b0, 1 - b0 - b2, b2], 1)


def ls_stops(t: np.ndarray, colors: np.ndarray) -> tuple[np.ndarray, float]:
    """Best stop colors (3, C) for coordinates t and their mean squared render error."""
    B = _hat(t)
    S, *_ = np.linalg.lstsq(B, colors, rcond=None)
    S = np.clip(S, 0, 255)
    return S, float(((B @ S - colors) ** 2).mean())


def _normalize(r: np.ndarray) -> tuple[np.ndarray, float]:
    lo_hi = np.percentile(r, [0.5, 99.5])
    return np.clip((r - lo_hi[0]) / max(lo_hi[1] - lo_hi[0], 1e-9), 0, 1), lo_hi


def linear_model(ys: np.ndarray, xs: np.ndarray, colors: np.ndarray):
    """Direction of strongest color change. Returns (t, (x1, y1, x2, y2)) or None for (almost) no extent."""
    A = np.stack([np.ones_like(xs), xs, ys], axis=1).astype(np.float64)
    coef, *_ = np.linalg.lstsq(A, colors.astype(np.float64), rcond=None)
    _, _, vt = np.linalg.svd(coef[1:3].T)
    d = vt[0]
    t, (t0, t1) = _normalize(xs * d[0] + ys * d[1])
    if t1 - t0 < 4:
        return None
    cx, cy = xs.mean(), ys.mean()
    tc = cx * d[0] + cy * d[1]
    return t, (cx + (t0 - tc) * d[0], cy + (t0 - tc) * d[1], cx + (t1 - tc) * d[0], cy + (t1 - tc) * d[1])


def radial_model(ys: np.ndarray, xs: np.ndarray, colors: np.ndarray, init: tuple | None = None):
    """Elliptical radial model for blob shading (ball, blush, glow): the main color axis grows linearly with the
    elliptical distance from a center inside the region (a cone). The quadratic least-squares surface gives the
    start (or `init`, a previous fit's (cx, cy, angle, log axis ratio) in pixels); a non-linear fit then refines
    center and ellipse. Returns (t, 2x3 gradientTransform, params) or None."""
    c = colors - colors.mean(axis=0)
    step = max(1, len(c) // _SAMPLE)
    _, _, vt = np.linalg.svd(c[::step], full_matrices=False)
    v = c @ vt[0]
    mx, my = xs.mean(), ys.mean()
    sc = max(xs.std(), ys.std(), 1.0)
    u, w = (xs - mx) / sc, (ys - my) / sc
    if init is not None:
        start = [(init[0] - mx) / sc, (init[1] - my) / sc, init[2], init[3]]
        lim = 3.0
    else:
        start, lim = _quadratic_start(u, w, v, step), 1.5
        if start is None:
            return None
    return _cone_fit(u, w, v, step, start, lim, mx, my, sc)


def _quadratic_start(u, w, v, step):
    """Center/ellipse of the quadratic bowl/dome through the shading, or None for a saddle, ridge or an extremum
    outside the region."""
    Q = np.stack([np.ones_like(u), u, w, u * u, u * w, w * w], 1)
    k, *_ = np.linalg.lstsq(Q[::step], v[::step], rcond=None)
    H = np.array([[2 * k[3], k[4]], [k[4], 2 * k[5]]])
    ev = np.linalg.eigvalsh(H)
    if ev[0] * ev[1] <= 0 or min(abs(ev)) < 0.15 * max(abs(ev)):   # saddle or ridge: not a blob
        return None
    H = H * np.sign(ev[0])
    ctr = -np.linalg.solve(H, k[1:3] * np.sign(ev[0]))
    if abs(ctr[0]) > 1.5 or abs(ctr[1]) > 1.5:                      # extremum must lie within the region
        return None
    lam, V = np.linalg.eigh(H)
    return [ctr[0], ctr[1], np.arctan2(V[1, 0], V[0, 0]), float(np.clip(0.25 * np.log(lam[1] / lam[0]), -1, 1))]


def _cone_fit(u, w, v, step, start, lim, mx, my, sc):
    us, ws, vs = u[::step], w[::step], v[::step]

    def dist(prm, uu, ww):
        cx, cy, th, s = prm
        du, dw = uu - cx, ww - cy
        a = du * np.cos(th) + dw * np.sin(th)
        b = -du * np.sin(th) + dw * np.cos(th)
        return np.sqrt(a * a * np.exp(-2 * s) + b * b * np.exp(2 * s))

    def resid(prm):
        r = dist(prm, us, ws)
        A = np.stack([np.ones_like(r), r], 1)
        kk, *_ = np.linalg.lstsq(A, vs, rcond=None)
        return A @ kk - vs

    start = [float(np.clip(start[0], -lim, lim)), float(np.clip(start[1], -lim, lim)), start[2],
             float(np.clip(start[3], -1.2, 1.2))]
    fit = optimize.least_squares(resid, start, bounds=([-lim, -lim, -np.inf, -1.2], [lim, lim, np.inf, 1.2]),
                                 max_nfev=40)
    cx, cy, th, s = fit.x
    r = dist(fit.x, u, w)
    R = np.percentile(r, 99.5)
    if R <= 0:
        return None
    t = np.clip(r / R, 0, 1)
    # unit circle -> ellipse in pixel units: rotate(th) * scale(R e^s, R e^-s), then translate to the center
    a1, a2 = R * np.exp(s) * sc, R * np.exp(-s) * sc
    m = (np.cos(th) * a1, np.sin(th) * a1, -np.sin(th) * a2, np.cos(th) * a2, mx + cx * sc, my + cy * sc)
    return t, m, (mx + cx * sc, my + cy * sc, th, s)


def radial_residuals(ys: np.ndarray, xs: np.ndarray, colors: np.ndarray, init: tuple | None = None):
    """(per-pixel squared render error of the best radial gradient, its params), or None if not a blob."""
    rad = radial_model(ys + 0.5, xs + 0.5, colors, init)
    if rad is None:
        return None
    S, _ = ls_stops(rad[0], colors)
    return ((_hat(rad[0]) @ S - colors) ** 2).mean(axis=1), rad[2]


def _num(v: float) -> str:
    return f'{v:.2f}'.rstrip('0').rstrip('.')


def fit_fill(ys: np.ndarray, xs: np.ndarray, colors: np.ndarray, gid: str, flat_de: float, min_area: int = 300,
             radial: bool = True):
    """Fill for one region: solid, linear gradient, or (when it fits clearly better, -20 % error) elliptical radial
    gradient. Returns (fill attribute value, gradient markup or ''), in source-pixel coordinates."""
    colors = colors.astype(np.float64)
    mean = colors.mean(axis=0)
    if len(colors) < max(min_area, 30):
        return to_hex(mean), ''
    best = None                                  # (mse, kind, stops, geometry)
    lin = linear_model(ys, xs, colors)
    if lin is not None:
        S, e = ls_stops(lin[0], colors)
        best = (e, 'linear', S, lin[1])
    if radial and (best is None or best[0] >= 4.0):    # skip when a linear gradient is already near-exact
        rad = radial_model(ys, xs, colors)
        if rad is not None:
            S, e = ls_stops(rad[0], colors)
            if best is None or e < 0.8 * best[0]:
                best = (e, 'radial', S, rad[1])
    if best is None:
        return to_hex(mean), ''
    mse, kind, S, geo = best
    lab = to_lab(S.astype(np.float32))
    weak = np.linalg.norm(lab[0] - lab[2]) < flat_de and np.linalg.norm(lab[0] - lab[1]) < flat_de
    if weak or mse > GAIN * float(((colors - mean) ** 2).mean()):   # barely better than a solid fill
        return to_hex(mean), ''
    stops = ''.join(f'<stop offset="{o}" stop-color="{to_hex(c)}"/>' for o, c in zip(('0', '.5', '1'), S))
    if kind == 'radial':
        return f'url(#{gid})', (f'<radialGradient id="{gid}" gradientUnits="userSpaceOnUse" cx="0" cy="0" r="1" '
                                f'gradientTransform="matrix({" ".join(_num(v) for v in geo)})">{stops}</radialGradient>')
    x1, y1, x2, y2 = geo
    return f'url(#{gid})', (f'<linearGradient id="{gid}" gradientUnits="userSpaceOnUse" x1="{x1:.1f}" y1="{y1:.1f}" '
                            f'x2="{x2:.1f}" y2="{y2:.1f}">{stops}</linearGradient>')
