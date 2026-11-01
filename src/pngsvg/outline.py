"""Outline (ink line) separation by color unmixing.

Every pixel near an outline is modelled as a blend of the ink color I and the color behind it B:
    p = alpha * I + (1 - alpha) * B
B is taken from the nearest pixel outside the outline band. If p lies close to the segment I->B, alpha is its
position on that segment (anti-aliasing / soft edge); otherwise p is a genuine color (lips, nose, blush) and gets
alpha 0. The resulting continuous alpha map gives sub-pixel accurate, smooth outlines when upsampled, and the
same model lets the fill layer replace outline pixels with the color behind them.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from scipy import ndimage

from .color import delta_e, to_lab


@dataclass
class OutlineParams:
    core_de: float = 9.0        # Delta E to ink color below which a pixel is pure ink
    dark_margin: float = 3.0    # pixels darker (L*) than ink L* + margin are always ink (ink blended with deep reds)
    thin_size: int = 7          # thin lines (anti-aliased, never reaching full ink): black top-hat window...
    thin_depth: float = 25.0    # ...L* darker than their surroundings by at least this...
    thin_ab: float = 16.0       # ...with ink-like hue (a*b* distance), so brown wrinkles / grey brows stay color
    band: int = 5               # px around ink cores examined for blending
    residual: float = 36.0      # max RGB distance from the I->B segment to count as a blend
    ink_line_size: int = 21     # lines thinner than this (px) define the ink color...
    ink_chroma: float = 15.0    # a darkest-pixel color with more chroma (a*b*) than this is checked against lines:
    ink_line_fraction: float = 0.4  # use line pixels when fewer of the darkest pixels than this are lines...
    ink_line_pct: float = 5.0   # ...and take the darkest N % of them (line cores; darker is the safer error)
    ink_percentile: float = 2.0  # ink color = median of the darkest N% pixels (halved down to 0.5 % if too light)
    max_ink_l: float = 35.0     # if the darkest pixels are lighter than this L*, the image has no outlines
    halo_px: int = 3            # sharpening halos: within this distance of ink...
    halo_ab: float = 12.0       # ...same hue as the color behind (a*b* distance below this)...
    halo_l: float = 30.0        # ...and lighter by at most this much L* -> flattened to the color behind
    max_ink_width: float = 24.0  # ink is drawn as strokes: core parts wider than this (px) with shading of their
                                 #    own are dark AREAS and stay fills (a reflection on a black screen); 0 = off
    shaded_area: float = 0.1    # ...when more than this share of the area is not ink-colored (Delta E > core_de / 2)
    ink_split_de: float = 15.0  # a stroke whose own color is this far (Delta E) from the ink gets its own ink color
    max_inks: int = 3           # ...up to this many ink colors (grey lines next to black ones stay grey)
    min_stroke: int = 40        # strokes smaller than this (px) take the main ink


@dataclass
class Outline:
    alpha: np.ndarray           # HxW float32, 0..1 ink coverage
    ink_rgb: np.ndarray         # (3,) main ink color
    behind_rgb: np.ndarray      # HxWx3 uint8: image with ink removed (color behind the outline)
    inks: np.ndarray = field(default_factory=lambda: np.zeros((0, 3), np.float32))   # (m, 3): main ink first
    which: np.ndarray | None = None  # HxW int: the ink of each pixel (index into inks)


def detect_ink(rgb: np.ndarray, lab: np.ndarray, p: OutlineParams):
    """Ink color = median of the darkest pixels. When that color is clearly chromatic and those pixels are mostly
    large dark AREAS rather than lines (a dark purple flag, deep blue water), the ink is taken from line pixels instead - pixels darker than their
    surroundings, i.e. structures thinner than ink_line_size - so the outline layer gets the color of the lines."""
    L = lab[..., 0]
    pct = p.ink_percentile
    cut = np.percentile(L, pct)
    while cut > p.max_ink_l and pct > 0.3:     # thin outlines on a big image cover < 2 % of the pixels:
        pct /= 2                                # look at an even darker tail before concluding there is no ink
        cut = np.percentile(L, pct)
    if cut > p.max_ink_l:
        return None
    darkest = L <= cut
    ink = np.median(rgb[darkest], axis=0).astype(np.float32)
    chroma = float(np.hypot(*to_lab(ink)[1:]))
    if chroma < p.ink_chroma:                   # near-neutral (black) ink: right for line art even when the
        return ink                              # darkest pixels are hair or a night sky
    line = (ndimage.grey_closing(L, size=p.ink_line_size) - L) > p.thin_depth
    if (line & darkest).sum() < p.ink_line_fraction * darkest.sum() and line.sum() >= max(200, 0.002 * L.size):
        lcut = np.percentile(L[line], p.ink_line_pct)
        if lcut <= p.max_ink_l:
            return np.median(rgb[line & (L <= lcut)], axis=0).astype(np.float32)
    return ink


def stroke_inks(core: np.ndarray, rgb: np.ndarray, lab: np.ndarray, ink: np.ndarray,
                p: OutlineParams) -> tuple[np.ndarray, np.ndarray]:
    """Ink color per stroke: every connected piece of the ink core takes the median of its darkest half; pieces
    clearly different from the main ink (thin grey lines among black ones) are grouped into up to max_inks - 1 more
    ink colors. Returns (inks (m, 3), ink index per core pixel, -1 elsewhere)."""
    which = np.full(core.shape, -1, np.int64)
    inks = [ink.astype(np.float32)]
    comp, n = ndimage.label(core)
    if n == 0 or p.max_inks < 2:
        which[core] = 0
        return np.array(inks), which
    pieces = []
    for i, box in enumerate(ndimage.find_objects(comp), 1):
        sel = comp[box] == i
        size = int(sel.sum())
        L = lab[box][..., 0][sel]
        dark = L <= np.percentile(L, 50)
        color = np.median(rgb[box][sel][dark], axis=0).astype(np.float32)
        pieces.append((size, i, box, sel, color))
    sizes: list[float] = [0.0]
    sums = [np.zeros(3, np.float64)]
    for size, i, box, sel, color in sorted(pieces, key=lambda t: -t[0]):
        k = 0
        if size >= p.min_stroke and float(delta_e(to_lab(color), to_lab(ink))) >= p.ink_split_de:
            dist = [float(delta_e(to_lab(color), to_lab(inks[j]))) for j in range(1, len(inks))]
            near = int(np.argmin(dist)) + 1 if dist else 0
            if dist and dist[near - 1] < p.ink_split_de:
                k = near
            elif len(inks) < p.max_inks:
                inks.append(color)
                sizes.append(0.0)
                sums.append(np.zeros(3, np.float64))
                k = len(inks) - 1
        if k:
            sizes[k] += size
            sums[k] += color * size
            inks[k] = (sums[k] / sizes[k]).astype(np.float32)
        which[box][sel] = k
    return np.array(inks), which


def separate(rgb: np.ndarray, p: OutlineParams | None = None) -> Outline:
    p = p or OutlineParams()
    lab = to_lab(rgb)
    ink = detect_ink(rgb, lab, p)
    if ink is None:
        return Outline(np.zeros(rgb.shape[:2], np.float32), np.zeros(3, np.float32), rgb.copy())
    ink = ink.astype(np.float32)
    ink_lab = to_lab(ink)
    L = lab[..., 0]
    tophat = ndimage.grey_closing(L, size=p.thin_size) - L          # local darkness of thin structures
    thin = (tophat > p.thin_depth) & (np.linalg.norm(lab[..., 1:] - ink_lab[1:], axis=-1) < p.thin_ab)
    core = (delta_e(lab, ink_lab) < p.core_de) | (L < ink_lab[0] + p.dark_margin) | thin
    core = ndimage.binary_opening(core, iterations=1) | (core & (lab[..., 0] < ink_lab[0] + p.dark_margin))
    if p.max_ink_width > 0:
        # ink is a stroke: where the core is wider than a stroke can be AND has shading of its own (a reflection on
        # a black screen, light in dark hair), it is a dark area of the picture and stays a fill. A flat ink-colored
        # area (a black spot) stays ink: drawing it as a fill would only cost bytes.
        half = p.max_ink_width / 2
        wide = ndimage.distance_transform_edt(core) > half
        if wide.any():
            area = ndimage.binary_dilation(wide, iterations=int(math.ceil(half)) + 1) & core
            pieces, n = ndimage.label(area)
            off = delta_e(lab, ink_lab)
            for i, box in enumerate(ndimage.find_objects(pieces), 1):
                sel = pieces[box] == i
                if (off[box][sel] > p.core_de / 2).mean() > p.shaded_area:
                    core[box] &= ~sel
    if not core.any():
        return Outline(np.zeros(rgb.shape[:2], np.float32), ink, rgb.copy(), ink[None], np.zeros(rgb.shape[:2], np.int64))
    inks, which_core = stroke_inks(core, rgb, lab, ink, p)
    _, (ky, kx) = ndimage.distance_transform_edt(~core, return_indices=True)
    which = which_core[ky, kx]                                       # every pixel: the ink of the nearest stroke
    ink_px = inks[which]

    band = ndimage.binary_dilation(core, iterations=p.band)
    _, (iy, ix) = ndimage.distance_transform_edt(band, return_indices=True)
    px = rgb.astype(np.float32)
    behind = px[iy, ix]
    v = behind - ink_px
    t = np.clip(((px - ink_px) * v).sum(-1) / np.maximum((v * v).sum(-1), 1.0), 0.0, 1.0)
    resid = np.linalg.norm(px - (ink_px + t[..., None] * v), axis=-1)
    blend = band & ~core & (resid < p.residual)
    alpha = np.where(core, 1.0, np.where(blend, 1.0 - t, 0.0)).astype(np.float32)

    # Over-sharpened generators leave a light rim of the SAME hue next to the ink; flatten it to the color behind.
    lab_b = to_lab(behind)
    dl = lab[..., 0] - lab_b[..., 0]
    dab = np.linalg.norm(lab[..., 1:] - lab_b[..., 1:], axis=-1)
    near_ink = ndimage.distance_transform_edt(~core) <= p.halo_px
    halo = near_ink & ~core & ~blend & (dl > 0) & (dl < p.halo_l) & (dab < p.halo_ab)

    replace = (alpha > 0.02) | halo
    _, (jy, jx) = ndimage.distance_transform_edt(replace, return_indices=True)
    return Outline(alpha, ink, rgb[jy, jx], inks, which)


def outline_mask(alpha: np.ndarray, scale: int, threshold: float = 0.5, smooth: float = 0.6) -> np.ndarray:
    """Upsample the alpha map `scale` times (bilinear), smooth lightly, threshold -> crisp sub-pixel outline."""
    from PIL import Image
    h, w = alpha.shape
    big = np.asarray(Image.fromarray((alpha * 255).astype(np.uint8)).resize((w * scale, h * scale), Image.BILINEAR),
                     dtype=np.float32) / 255
    if smooth > 0:
        big = ndimage.gaussian_filter(big, sigma=scale * smooth)
    return big > threshold
