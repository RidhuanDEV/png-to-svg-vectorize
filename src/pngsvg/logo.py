"""Flat logo / icon engine: clean, small, animatable SVG from flat-color artwork.

Stages (each a pure function on explicit types; same input + options -> byte-identical SVG):

    load -> background -> quantize -> assign (anti-alias aware) -> clean -> shapes -> contours -> fit -> serialize

1. load: RGB(A) as float, opacity; pictures under 256 px are traced at 2x. A noisy picture (noise estimated from
   the picture itself) is smoothed first with an edge-preserving filter.
2. background: transparent pixels, or else the dominant border color within a CIEDE2000 tolerance (kept when the
   picture turns out not to be flat: there that color is part of the art). It never becomes a <rect> or a path.
3. quantize: k-means in CIELAB (k-means++ start, fixed seed) on the flat (non-edge) pixels; automatic k = the
   smallest one whose mean error and 99th-percentile error stay below the tolerances (at most 16); close clusters
   merged; or a fixed palette. Light halos (near-background rims hugging shapes) return to the background.
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
    quant_tolerance: float = 4.0       # automatic colors: mean CIE76 error per pixel the palette must stay below...
    tail_tolerance: float = 4.0        # ...and 99.8 % of the flat pixels below this (two shades in one color fail it)
    merge_tolerance: float = 7.0       # palette colors closer than this (CIEDE2000) become one
    max_auto_colors: int = 16
    shading_tolerance: float = 2.0     # mean RGB distance of all pixels to palette colors and their mixes: above it,
                                       # the picture has shading or texture (not a flat logo)
    halo_width: float = 5.0            # a color near the background (2x bg_tolerance) whose pixels lie within this
                                       # distance (px, 90 %) of its edge and that hugs other shapes (30 % of its
                                       # outline, 2 px gaps allowed) is a light halo of an older trace: it becomes
                                       # background (a thin light line on its own stays)
    denoise: float = 1.5               # estimated noise (levels, standard deviation) from which the picture is smoothed
                                       # with an edge-preserving filter before anything else; 0 = off
    min_area_ratio: float = 0.00003    # specks: smaller than this share of the content area (and min_area px) go
    split_shapes: bool = True          # split one-color pieces joined only by a neck thinner than neck_width px
    neck_width: float = 3.0
    corner_angle: float = 35.0         # a turn sharper than this (degrees) is a corner and stays sharp
    line_tolerance: float = 1.0        # a run between corners within this distance (px) of a line becomes a line
    bow_tolerance: float = 0.25        # ...unless it bows like an arc by more than this (px): then it is a curve
    conic_tolerance: float = 0.8       # a chain within this (px) of an ellipse, or of a circular arc through its ends,
                                       # becomes that exact curve; 0 = off
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
    guessed: bool = False              # from the border color (no transparency): only safe on flat artwork


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


def noise_level(rgb: np.ndarray) -> float:
    """Standard deviation (levels) of the picture's random noise.

    Immerkaer's 3x3 kernel (Immerkaer 1996) is zero on flat color and on any linear ramp, so only noise and edges
    respond; the median of its absolute response (instead of Immerkaer's mean) ignores the edges, which cover a small
    share of flat art. A clean logo scores 0, Gaussian noise of sigma s scores about 0.8 s."""
    r = (rgb[:-2, :-2] - 2 * rgb[:-2, 1:-1] + rgb[:-2, 2:] - 2 * rgb[1:-1, :-2] + 4 * rgb[1:-1, 1:-1]
         - 2 * rgb[1:-1, 2:] + rgb[2:, :-2] - 2 * rgb[2:, 1:-1] + rgb[2:, 2:])
    return float(np.median(np.abs(r))) / (6 * 0.6745) if r.size else 0.0


def bilateral(rgb: np.ndarray, sigma: float, radius: int = 2, spatial: float = 1.5) -> tuple[np.ndarray, float]:
    """Edge-preserving smoothing (Tomasi & Manduchi 1998): every neighbour within `radius` px is weighted by its
    distance and by its color difference (scale 3 sigma), so noise averages out but an edge between two colors,
    far more than 3 sigma apart, stays sharp. Also returns the factor by which it reduced independent noise
    (the median over the pixels of sqrt(sum w^2) / sum w)."""
    h, w = rgb.shape[:2]
    pad = np.pad(rgb, ((radius, radius), (radius, radius), (0, 0)), mode='edge')
    acc = np.zeros_like(rgb)
    total = np.zeros((h, w))
    squares = np.zeros((h, w))
    s2 = 2 * (3 * sigma) ** 2
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            nb = pad[radius + dy:radius + dy + h, radius + dx:radius + dx + w]
            wgt = math.exp(-(dx * dx + dy * dy) / (2 * spatial ** 2)) * np.exp(-((nb - rgb) ** 2).sum(-1) / s2)
            acc += wgt[..., None] * nb
            total += wgt
            squares += wgt * wgt
    return acc / total[..., None], float(np.median(np.sqrt(squares) / total))


def denoise(rgb: np.ndarray, p: LogoParams) -> tuple[np.ndarray, float]:
    """Smooth a noisy picture (scan, photo of a print, noisy export) so its flat colors are flat again: noise makes
    every pixel an edge, and the palette, the background and the shapes all fall apart (a flag under noise of 16
    levels: 37 % of it visibly wrong). Strong noise gets a second pass. Returns the picture and the noise left
    (levels, standard deviation): what the shading check must not count as shading."""
    s = noise_level(rgb)
    if p.denoise <= 0 or s < p.denoise:
        return rgb, s
    rgb, gain = bilateral(rgb, max(s, 2.0))
    left = s * gain
    if s >= 6:
        rgb, _ = bilateral(rgb, max(noise_level(rgb), s / 3, 2.0))
        left /= math.sqrt(2)              # two Gaussian passes act as one, sqrt(2) wider: noise falls by sqrt(2) more
    return rgb, left


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
    return Background(mask, color, guessed=True)


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


def mix_residual(px: np.ndarray, colors: np.ndarray) -> np.ndarray:
    """RGB distance of each pixel to the closest color or mix of two colors (anti-aliasing between them)."""
    best = ((px[:, None] - colors[None]) ** 2).sum(-1).min(1)
    for i in range(len(colors)):
        for j in range(i + 1, len(colors)):
            ab = colors[i] - colors[j]
            den = float(ab @ ab)
            if den > 0:
                t = np.clip(((px - colors[j]) @ ab) / den, 0, 1)
                best = np.minimum(best, ((px - (colors[j] + t[:, None] * ab)) ** 2).sum(1))
    return np.sqrt(best)


PIXEL_EXACT = 64


def quantize(rgb: np.ndarray, fg: np.ndarray, p: LogoParams, max_colors: int | None,
             palette: tuple[str, ...] | None, edge_color: np.ndarray | None = None, noise: float = 0.0) -> Palette:
    warnings: list[str] = []
    if palette:
        fixed = np.array([[int(h[i:i + 2], 16) for i in (1, 3, 5)] for h in palette], np.float64)
        return Palette(fixed, warnings)
    if p.pixel and not max_colors:
        # pixel art has no anti-aliasing: every color is meant, also a single pixel or a checkerboard (whose pixels all
        # touch another color and would never count as flat). Up to PIXEL_EXACT colors are taken exactly.
        colors, counts = np.unique(np.round(rgb[fg]), axis=0, return_counts=True)
        if 0 < len(colors) <= PIXEL_EXACT:
            return Palette(colors[np.argsort(-counts, kind='stable')], warnings)
    sample = flat_pixels(rgb, fg)
    if len(sample) == 0:
        return Palette(np.zeros((0, 3)), ['no foreground found'])
    lab = to_lab(sample).astype(np.float64)
    if max_colors:
        centers, assign = _kmeans(lab, max_colors)
    else:
        prev_tail, stall = math.inf, 0
        for k in range(1, p.max_auto_colors + 1):
            centers, assign = _kmeans(lab, k)
            dist = np.linalg.norm(lab - centers[assign], axis=1)
            err = float(dist.mean())
            tail = float(np.percentile(dist, 99.8))       # a color on 0.2 % of the art (a flag's white band) counts
            if err < p.quant_tolerance:
                if tail < p.tail_tolerance:
                    break
                stall = stall + 1 if tail > 0.9 * prev_tail else 0
                if stall >= 2:                            # noise (JPEG ringing), not colors: more clusters stop helping
                    break
            prev_tail = tail
        else:
            if err >= p.quant_tolerance:
                    warnings.append(f'more than {p.max_auto_colors} colors (mean error {err:.1f}): this picture is not a '
                                'flat logo; the illustration or cartoon style keeps more detail')
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
        # every pixel should be a palette color or an anti-aliased mix of two (or of one and the background):
        # line art is almost only such mixes, shading and texture are not. Random noise (left after denoise())
        # adds its own mean distance, about 1.6 sigma over 3 channels, and is not shading.
        colors = centers_rgb if edge_color is None else np.vstack([centers_rgb, edge_color[None]])
        err_all = float(mix_residual(allfg, colors).mean())
        if err_all > p.shading_tolerance + 1.6 * noise:
            warnings.append(f'the picture has shading or many colors (mean error {err_all:.1f}): it is not a flat '
                            'logo; the illustration or cartoon style keeps more detail')
    return Palette(centers_rgb, warnings)


def palette_with_background(rgb: np.ndarray, alpha: np.ndarray | None, p: LogoParams,
                            noise: float = 0.0) -> Palette | None:
    """Background kept: the palette of the art without it, plus the background color (None: one palette for all).

    The background is usually the largest flat color: in the k-means sample it crowds out the art's own colors (a
    shop icon on white lost 3 of its 10). So the art is quantized as if the background were removed, and the
    background color is added, with a light color close to it (#ECF0F1 on white) if it has one."""
    guess = background(rgb, alpha, p, False)
    if not guess.mask.any() or guess.mask.all():
        return None
    pal = quantize(rgb, ~guess.mask, p, None, None, guess.color, noise)
    if pal.warnings or len(pal.rgb) == 0:
        return None                     # not flat: the border color is part of the art
    color = np.round(guess.color)
    # the background is a palette color now, and like any pair, colors closer than merge_tolerance are one: here
    # the rim of compression noise around it (JPEG), which the background mask no longer covers
    art = pal.rgb[delta_e2000(to_lab(pal.rgb), to_lab(color)) >= p.merge_tolerance]
    light = color_near_background(rgb, guess, p)
    near = [color] if light is None else [color, light]
    return Palette(np.vstack([np.array(near), art]), pal.warnings)


def color_near_background(rgb: np.ndarray, bg: Background, p: LogoParams) -> np.ndarray | None:
    """A flat color within bg_tolerance of the background color, or None.

    Such a color falls inside the background mask. It is a color of its own when its flat pixels form a second peak
    in the distance to the background color, at least 3x the valley before it; compression noise around the
    background (JPEG) only thins out with the distance and has no such peak."""
    px = flat_pixels(rgb, bg.mask)
    de = delta_e2000(to_lab(px), to_lab(bg.color))
    width = 0.5
    hist, _ = np.histogram(de, bins=int(round(p.bg_tolerance / width)), range=(0.0, p.bg_tolerance))
    first = int(round(p.bg_tolerance / 3 / width))          # beyond the background color itself
    peak = first + int(np.argmax(hist[first:]))
    if hist[peak] < 64 or hist[peak] < 3 * hist[1:peak].min():
        return None
    sel = np.abs(de - (peak + 0.5) * width) <= width
    return np.round(np.median(px[sel], axis=0))


# ------------------------------------------------------------------------------------------------ 4. assign

MIX_MARGIN = 3 * 8.0 ** 2          # squared RGB distance a mix must beat the nearest pure color by (8 levels)


def assign(rgb: np.ndarray, bg: Background, pal: Palette, chunk: int = 1 << 18) -> np.ndarray:
    """Label per pixel: 0..k-1 palette colors, k background. Each pixel is matched to the closest mix t*A + (1-t)*B
    of two colors (a pure color is t = 1) and takes A if it covers at least half of the pixel."""
    h, w = rgb.shape[:2]
    k = len(pal.rgb)
    # the background takes part in edge mixes only when there is one: otherwise art of its color would turn transparent
    colors = np.vstack([pal.rgb, bg.color[None]]) if bg.mask.any() else pal.rgb
    out = np.full(h * w, k, np.int64)
    flat = rgb.reshape(-1, 3)
    todo = np.nonzero(~bg.mask.ravel())[0]
    pairs = [(i, j) for i in range(len(colors)) for j in range(i + 1, len(colors))] or [(0, 0)]
    for s in range(0, len(todo), chunk):
        idx = todo[s:s + chunk]
        px = flat[idx]
        # a pixel that IS a palette color stays that color: a mix must explain it clearly better (a flat grey lies
        # exactly on the black-white mix line, and was taken for anti-aliasing)
        pure = ((px[:, None] - colors[None]) ** 2).sum(-1)
        pick = np.argmin(pure, 1)
        best = pure[np.arange(len(idx)), pick] - MIX_MARGIN
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

def absorb_halos(label: np.ndarray, bg: Background, pal: Palette, p: LogoParams, scale: int) -> np.ndarray:
    """Colors close to the background that exist only as thin rims hugging other shapes become background."""
    k = len(pal.rgb)
    if not bg.mask.any() or k < 2:
        return label
    near = delta_e2000(to_lab(pal.rgb), to_lab(bg.color)) < 2 * p.bg_tolerance
    out = label.copy()
    shapes = (label < k)
    for c in np.nonzero(near)[0]:
        pieces, n = ndimage.label(label == c)
        for i, sl in enumerate(ndimage.find_objects(pieces), 1):
            sl = tuple(slice(max(0, x.start - 2), x.stop + 2) for x in sl)       # room for the neighbours
            piece = pieces[sl] == i
            thin = np.percentile(ndimage.distance_transform_edt(piece)[piece], 90) <= p.halo_width * scale
            rim = piece & ~ndimage.binary_erosion(piece)
            hugs = (rim & ndimage.binary_dilation(shapes[sl] & ~piece, iterations=2)).sum() >= 0.3 * rim.sum()
            if thin and hugs:
                out[sl][piece] = k
    return out


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


def false_edges(label: np.ndarray, rgb: np.ndarray, k: int) -> float:
    """Share of the borders between two colors that run through smooth color (neighbours across the border closer
    than 3 Delta E): a gradient cut into flat bands. A real edge, even anti-aliased, has a clear step there."""
    lab = to_lab(rgb).astype(np.float64)
    steps = []
    for axis in (0, 1):
        a = label[:-1] if axis == 0 else label[:, :-1]
        b = label[1:] if axis == 0 else label[:, 1:]
        cross = (a != b) & (a < k) & (b < k)
        diff = (lab[:-1] - lab[1:]) if axis == 0 else (lab[:, :-1] - lab[:, 1:])
        steps.append(np.linalg.norm(diff[cross], axis=-1))
    step = np.concatenate(steps)
    return float((step < 3.0).mean()) if len(step) else 0.0


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
    thick = ndimage.binary_opening(piece, structure=disk)
    if (piece & ~thick).sum() > 0.5 * piece.sum():      # mostly thin: a stroke (a ring, a line), not shapes on a neck
        return piece.astype(np.int64)
    cores, m = ndimage.label(thick)
    if m >= 2:                                          # specks of a slightly thicker stroke are not parts
        size = np.bincount(cores.ravel())
        small = np.nonzero(size < max(64, (4 * r) ** 2))[0]
        cores = np.where(np.isin(cores, small), 0, cores)
        cores, m = ndimage.label(cores > 0)
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
class _Conic:
    """A whole chain that is an exact ellipse (closed) or circular arc (open, through both of its ends)."""
    centre: np.ndarray
    axes: tuple[float, float]   # semi-axes; equal for a circle
    angle: float                # rotation of the first axis (radians)
    start: float                # parameter angle of the first point
    sweep: float                # signed parameter sweep (2 pi for a closed ellipse)


@dataclass
class _ChainFit:
    closed: bool
    pts: np.ndarray
    corners: list[int]          # indices into pts (open chains: include both ends)
    runs: list[_Run]
    conic: _Conic | None = None


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


def _bowed(pts: np.ndarray, line: _Line, limit: float) -> bool:
    """A run within the line tolerance can still be a gentle curve: its residual is then systematic (all on one side,
    largest in the middle) where a straight but noisy edge has a random one. True when a parabola explains most of
    the residual and bulges more than `limit` px."""
    if limit <= 0 or len(pts) < 8:
        return False
    rel = pts - line.centre
    s = rel @ line.direction
    d = rel @ np.array([-line.direction[1], line.direction[0]])
    a, b, c = np.polyfit(s, d, 2)
    fit = (a * s + b) * s + c
    total = float(((d - d.mean()) ** 2).sum())
    explained = 1 - float(((d - fit) ** 2).sum()) / total if total > 1e-9 else 0.0
    sagitta = abs(a) * (float(s.max() - s.min()) / 2) ** 2
    return explained > 0.6 and sagitta > limit


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
        body = seg[trim:len(seg) - trim] if trim else seg
        line, dev = _fit_line(body)
        if dev > p.line_tolerance or _bowed(body, line, p.bow_tolerance):
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


def _cap_line(gap: np.ndarray, a: _Line, b: _Line, tol: float) -> _Line | None:
    """The straight short side between two parallel lines (a square bar end), or None when it is rounded. Points
    still on either line (and the sub-pixel chamfer at the corners) are not part of it."""
    off = [np.abs((gap - l.centre) @ np.array([-l.direction[1], l.direction[0]])) for l in (a, b)]
    inner = gap[(off[0] > tol) & (off[1] > tol)]
    if len(inner) < 2:                            # too short to judge: square, across the lines
        across = np.array([-a.direction[1], a.direction[0]])
        return _Line(gap.mean(0), across, float(np.linalg.norm(gap[-1] - gap[0])))
    line, dev = _fit_line(inner)
    return line if dev <= tol and abs(float(line.direction @ a.direction)) < math.cos(math.radians(60)) else None


def _ellipse_fit(pts: np.ndarray) -> tuple[np.ndarray, tuple[float, float], float] | None:
    """Direct least-squares ellipse (Fitzgibbon, Pilu & Fisher 1999) in the numerically stable form of Halir &
    Flusser (1998). Returns (centre, semi-axes, angle) or None."""
    c = pts.mean(0)
    scale = float(np.abs(pts - c).max()) or 1.0
    x, y = ((pts - c) / scale).T
    d1 = np.column_stack([x * x, x * y, y * y])
    d2 = np.column_stack([x, y, np.ones_like(x)])
    s1, s2, s3 = d1.T @ d1, d1.T @ d2, d2.T @ d2
    try:
        t = -np.linalg.solve(s3, s2.T)
    except np.linalg.LinAlgError:
        return None
    m = s1 + s2 @ t
    m = np.array([m[2] / 2, -m[1], m[0] / 2])
    _, vecs = np.linalg.eig(m)
    vecs = np.real(vecs)
    cond = 4 * vecs[0] * vecs[2] - vecs[1] ** 2
    if not (cond > 0).any():
        return None
    a1 = vecs[:, int(np.argmax(cond > 0))]
    a, b, cc, dd, e, f = np.concatenate([a1, t @ a1])
    b, dd, e = b / 2, dd / 2, e / 2
    den = b * b - a * cc
    if den >= 0:
        return None
    x0, y0 = (cc * dd - b * e) / den, (a * e - b * dd) / den
    num = 2 * (a * e * e + cc * dd * dd + f * b * b - 2 * b * dd * e - a * cc * f)
    root = math.sqrt((a - cc) ** 2 + 4 * b * b)
    r1, r2 = num / (den * (root - (a + cc))), num / (den * (-root - (a + cc)))
    if r1 <= 0 or r2 <= 0:
        return None
    ang = 0.5 * math.atan2(-2 * b, cc - a)
    return c + scale * np.array([x0, y0]), (scale * math.sqrt(r1), scale * math.sqrt(r2)), ang


def _conic_points(k: _Conic, n: int) -> np.ndarray:
    t = k.start + k.sweep * np.linspace(0, 1, n)
    ca, sa = math.cos(k.angle), math.sin(k.angle)
    u, v = k.axes[0] * np.cos(t), k.axes[1] * np.sin(t)
    return k.centre + np.column_stack([u * ca - v * sa, u * sa + v * ca])


def _param(k: _Conic, q: np.ndarray) -> np.ndarray:
    ca, sa = math.cos(k.angle), math.sin(k.angle)
    d = q - k.centre
    return np.arctan2((-d[..., 0] * sa + d[..., 1] * ca) / k.axes[1], (d[..., 0] * ca + d[..., 1] * sa) / k.axes[0])


def _deviation(pts: np.ndarray, k: _Conic) -> float:
    """Largest distance of the points to the conic (a dense polyline of it)."""
    curve = _conic_points(k, max(64, int(abs(k.sweep) * max(k.axes) / 2)))
    a, ab = curve[:-1], curve[1:] - curve[:-1]
    best = np.full(len(pts), np.inf)
    for i in range(0, len(a), 256):
        aa, bb = a[i:i + 256], ab[i:i + 256]
        t = np.clip(((pts[:, None] - aa[None]) * bb[None]).sum(-1) / np.maximum((bb * bb).sum(1), 1e-12)[None], 0, 1)
        best = np.minimum(best, np.linalg.norm(pts[:, None] - (aa[None] + t[..., None] * bb[None]), axis=-1).min(1))
    return float(best.max())


def _find_conic(pts: np.ndarray, closed: bool, p: LogoParams) -> _Conic | None:
    """Regularity: a closed chain that is an ellipse, or an open chain that is a circular arc through its two ends,
    becomes that exact curve (round eyes, dots and rings stay round instead of nearly round)."""
    if p.conic_tolerance <= 0 or len(pts) < 16:
        return None
    if closed:
        e = _ellipse_fit(pts)
        if e is None or min(e[1]) < 2 or max(e[1]) > 20 * min(e[1]):
            return None
        c, axes, ang = e
        if abs(axes[0] - axes[1]) < 0.01 * max(axes):            # a circle: no orientation to keep
            axes, ang = (float(np.mean(axes)),) * 2, 0.0
        k = _Conic(c, (float(axes[0]), float(axes[1])), ang, 0.0, 2 * math.pi)
        t = np.unwrap(_param(k, pts))
        k.start, k.sweep = float(t[0]), 2 * math.pi * (1 if t[-1] > t[0] else -1)
    else:
        p0, p1 = pts[0], pts[-1]
        chord = float(np.linalg.norm(p1 - p0))
        if chord < 4:
            return None
        mid, nrm = (p0 + p1) / 2, np.array([-(p1 - p0)[1], (p1 - p0)[0]]) / chord
        rel = pts - mid
        # circles through both ends have centres mid + s * nrm, and |q - c|^2 = r^2 is linear in s: least squares
        a = 2 * (rel @ nrm)
        b = (rel * rel).sum(1) - (chord / 2) ** 2
        if float(a @ a) < 1e-9:
            return None
        s = float(a @ b) / float(a @ a)
        r = math.hypot(chord / 2, s)
        if r > 10 * chord:                                         # nearly straight: lines handle it
            return None
        k = _Conic(mid + s * nrm, (r, r), 0.0, 0.0, 0.0)
        t = np.unwrap(_param(k, pts))
        k.start, k.sweep = float(t[0]), float(t[-1] - t[0])
        if abs(k.sweep) < math.radians(20):
            return None
    return k if _deviation(pts, k) <= p.conic_tolerance else None


def _conic_segments(k: _Conic, first: np.ndarray, last: np.ndarray | None) -> list[Segment]:
    """Cubic Beziers of the conic in pieces of at most 90 degrees (error < 0.03 % of the radius); exact end points."""
    n = max(1, math.ceil(abs(k.sweep) / (math.pi / 2) - 1e-9))
    step = k.sweep / n
    h = 4 / 3 * math.tan(step / 4)
    ca, sa = math.cos(k.angle), math.sin(k.angle)

    def at(t: float) -> np.ndarray:
        u, v = k.axes[0] * math.cos(t), k.axes[1] * math.sin(t)
        return k.centre + np.array([u * ca - v * sa, u * sa + v * ca])

    def tangent(t: float) -> np.ndarray:
        u, v = -k.axes[0] * math.sin(t) * h, k.axes[1] * math.cos(t) * h
        return np.array([u * ca - v * sa, u * sa + v * ca])

    segs = []
    for i in range(n):
        t0, t1 = k.start + i * step, k.start + (i + 1) * step
        q0 = first if i == 0 else at(t0)
        q3 = (first if last is None else last) if i == n - 1 else at(t1)
        segs.append(Segment('C', [tuple(map(float, q0)), tuple(map(float, at(t0) + tangent(t0))),
                                  tuple(map(float, at(t1) - tangent(t1))), tuple(map(float, q3))]))
    return segs


def analyse(chain: Chain, pts: np.ndarray, p: LogoParams, window: int) -> _ChainFit:
    """Corners and runs of one chain: straight lines (meeting at sharp corners) and curves in between."""
    closed = chain.closed
    n = len(pts)
    conic = None if p.pixel else _find_conic(pts, closed, p)
    if conic is not None:
        return _ChainFit(closed, pts, [] if closed else [0, n - 1], [], conic)
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
    caps: set[int] = set()
    for i in range(m if closed else m - 1):
        j = (i + 1) % m
        gap = _span(n, ends[i], starts[j], closed)
        if gap <= short_gap and _parallel(lines[i], lines[j], 30):
            caps.add(i)                           # a U-turn (end of a thin bar): parallel lines never meet, the gap
        elif gap <= short_gap:                    # is the bar's short side; else a corner (possibly slightly
            c = (ends[i] + gap // 2) % n          # rounded): the lines meet at one point
            ends[i], starts[j] = c, c
    if not closed and starts[0] > 0:
        curve(0, starts[0])
    for i in range(m):
        runs.append(_Run(starts[i], ends[i], lines[i].line))
        if closed or i + 1 < m:
            nxt = starts[(i + 1) % m]
            cap = _cap_line(_run_points(pts, ends[i], nxt), lines[i].line, lines[(i + 1) % m].line,
                            p.line_tolerance) if i in caps else None
            if cap is not None:
                runs.append(_Run(ends[i], nxt, cap))               # a square end
            elif nxt != ends[i]:
                curve(ends[i], nxt)                                 # a rounded end, or the curve between two lines
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
    if fit.conic is not None:
        return _conic_segments(fit.conic, pts[0], None if fit.closed else pts[-1])
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


def labels(rgb: np.ndarray, bg: Background, pal: Palette, p: LogoParams, scale: int, min_area: int) -> np.ndarray:
    """Stages 4-5: a label per pixel (len(pal.rgb) = background), halos absorbed, majority filter, specks removed."""
    k = len(pal.rgb)
    label = assign(rgb, bg, pal)
    label = absorb_halos(label, bg, pal, p, scale)
    if not p.pixel:
        label = majority(label, k + 1)
    content = int((label < k).sum())
    if not p.pixel:                       # in pixel art one pixel is a deliberate detail
        label = remove_specks(label, k + 1, max(min_area * scale * scale, int(p.min_area_ratio * content)))
    return label


def vectorize_logo(image: Image.Image, p: LogoParams, *, max_colors: int | None = None,
                   palette: tuple[str, ...] | None = None, keep_background: bool = False, decimals: int = 2,
                   color_groups: bool = False, min_area: int = 16,
                   tone: Callable[[np.ndarray], np.ndarray] | None = None,
                   stage: Callable[[str, float], None] | None = None) -> LogoResult:
    report = stage or (lambda name, fraction: None)
    report('ink', 0.05)
    rgb, alpha, scale = load(image, 0 if p.pixel else 256)
    noise = 0.0
    if not p.pixel:                       # pixel art is never noise: every pixel is meant
        rgb, noise = denoise(rgb, p)
    if tone is not None:
        rgb = tone(rgb)
    h, w = rgb.shape[:2]
    bg = background(rgb, alpha, p, keep_background)
    edge = bg.color if bg.mask.any() else None
    pal = None
    if keep_background and not palette and not max_colors and not p.pixel:
        pal = palette_with_background(rgb, alpha, p, noise)
    if pal is None:
        pal = quantize(rgb, ~bg.mask, p, max_colors, palette, edge, noise)
    kept = 'the background was kept: on a picture that is not flat, its color is part of the art'
    if bg.guessed and pal.warnings and not palette:
        # a painting or photo: its border color also fills the picture, removing it would punch holes
        bg = Background(np.zeros((h, w), bool), bg.color)
        pal = quantize(rgb, ~bg.mask, p, max_colors, palette, noise=noise)
        pal.warnings.append(kept)
    report('regions', 0.3)
    label = labels(rgb, bg, pal, p, scale, min_area)
    if not pal.warnings and not palette and not p.pixel and false_edges(label, rgb, len(pal.rgb)) > 0.05:
        gradient = ('smooth shading was cut into flat colors (a gradient): the illustration or cartoon style keeps it')
        if bg.guessed:                    # not flat either: same reason to keep the border color as above
            bg = Background(np.zeros((h, w), bool), bg.color)
            pal = quantize(rgb, ~bg.mask, p, max_colors, palette, noise=noise)
            label = labels(rgb, bg, pal, p, scale, min_area)
            pal.warnings[:0] = [gradient, kept]
        else:
            pal.warnings.append(gradient)
    k = len(pal.rgb)
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
