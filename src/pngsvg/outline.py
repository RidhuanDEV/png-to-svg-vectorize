"""Outline (ink line) separation by color unmixing.

Every pixel near an outline is modelled as a blend of the ink color I and the color behind it B:
    p = alpha * I + (1 - alpha) * B
B is taken from the nearest pixel outside the outline band. If p lies close to the segment I->B, alpha is its
position on that segment (anti-aliasing / soft edge); otherwise p is a genuine color (lips, nose, blush) and gets
alpha 0. The resulting continuous alpha map gives sub-pixel accurate, smooth outlines when upsampled, and the
same model lets the fill layer replace outline pixels with the color behind them.
"""
from __future__ import annotations

from dataclasses import dataclass

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
    ink_percentile: float = 2.0  # ink color = median of the darkest N% pixels
    max_ink_l: float = 35.0     # if the darkest pixels are lighter than this L*, the image has no outlines
    halo_px: int = 3            # sharpening halos: within this distance of ink...
    halo_ab: float = 12.0       # ...same hue as the color behind (a*b* distance below this)...
    halo_l: float = 30.0        # ...and lighter by at most this much L* -> flattened to the color behind


@dataclass
class Outline:
    alpha: np.ndarray           # HxW float32, 0..1 ink coverage
    ink_rgb: np.ndarray         # (3,) ink color
    behind_rgb: np.ndarray      # HxWx3 uint8: image with ink removed (color behind the outline)


def detect_ink(rgb: np.ndarray, lab: np.ndarray, p: OutlineParams):
    L = lab[..., 0]
    cut = np.percentile(L, p.ink_percentile)
    if cut > p.max_ink_l:
        return None
    return np.median(rgb[L <= cut], axis=0).astype(np.float32)


def separate(rgb: np.ndarray, p: OutlineParams | None = None) -> Outline:
    p = p or OutlineParams()
    lab = to_lab(rgb)
    ink = detect_ink(rgb, lab, p)
    if ink is None:
        return Outline(np.zeros(rgb.shape[:2], np.float32), np.zeros(3, np.float32), rgb.copy())
    ink_lab = to_lab(ink)
    L = lab[..., 0]
    tophat = ndimage.grey_closing(L, size=p.thin_size) - L          # local darkness of thin structures
    thin = (tophat > p.thin_depth) & (np.linalg.norm(lab[..., 1:] - ink_lab[1:], axis=-1) < p.thin_ab)
    core = (delta_e(lab, ink_lab) < p.core_de) | (L < ink_lab[0] + p.dark_margin) | thin
    core = ndimage.binary_opening(core, iterations=1) | (core & (lab[..., 0] < ink_lab[0] + p.dark_margin))

    band = ndimage.binary_dilation(core, iterations=p.band)
    _, (iy, ix) = ndimage.distance_transform_edt(band, return_indices=True)
    px = rgb.astype(np.float32)
    behind = px[iy, ix]
    v = behind - ink
    t = np.clip(((px - ink) * v).sum(-1) / np.maximum((v * v).sum(-1), 1.0), 0.0, 1.0)
    resid = np.linalg.norm(px - (ink + t[..., None] * v), axis=-1)
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
    return Outline(alpha, ink, rgb[jy, jx])


def outline_mask(alpha: np.ndarray, scale: int, threshold: float = 0.5, smooth: float = 0.6) -> np.ndarray:
    """Upsample the alpha map `scale` times (bilinear), smooth lightly, threshold -> crisp sub-pixel outline."""
    from PIL import Image
    h, w = alpha.shape
    big = np.asarray(Image.fromarray((alpha * 255).astype(np.uint8)).resize((w * scale, h * scale), Image.BILINEAR),
                     dtype=np.float32) / 255
    if smooth > 0:
        big = ndimage.gaussian_filter(big, sigma=scale * smooth)
    return big > threshold
