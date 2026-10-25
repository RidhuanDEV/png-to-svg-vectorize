"""Pipeline: raster cartoon illustration -> pure-path SVG (gradient fills + crisp outlines)."""
from __future__ import annotations

import re
from concurrent.futures import Executor
from typing import Callable
from dataclasses import dataclass, field

import numpy as np
from PIL import Image
from scipy import ndimage

from .color import to_hex, to_lab
from .curves import fit_chain
from .outline import Outline, OutlineParams, outline_mask, separate
from .planar import build_chains, loop_area, loops_to_path, region_loops, subpixel_offsets
from .gradients import fit_fill
from .regions import RegionParams, refine_boundaries, segment
from .pathdata import compact_path


@dataclass
class Options:
    scale: int | None = None          # tracing upscale; None = auto (long side ~4500 px)
    outlines: bool = True             # separate ink outlines into their own crisp layer
    gradients: bool = True            # gradient fills (False = flat colors)
    radial: bool = True               # allow elliptical radial gradients for blob-shaded regions
    smooth: float = 1.5               # fill boundary smoothing along the curve (sigma, source px)
    tolerance: float = 0.5            # max Bezier deviation from the smoothed fill boundary (source px)
    hidden_tolerance: float = 3.0     # ...where a fill boundary lies under the outline layer (invisible), up to this
    outline_smooth: float = 0.5       # the outline is already sub-pixel smooth: lighter smoothing keeps line tips
    outline_tolerance: float = 0.35
    subpixel: bool = True             # place fill boundaries at their sub-pixel edge position (from anti-aliasing)
    seam: float = 0.5                 # stroke width (source px) painted with each fill to hide anti-aliasing seams
    id_prefix: str = 'v'              # prefix for gradient ids (unique per file -> safe to inline many SVGs)
    decimals: int = 1                 # path coordinate decimals (0-3): fewer = smaller files
    max_colors: int | None = None     # at most this many flat colors, the ink included (None = free colors + gradients)
    palette: tuple[str, ...] | None = None  # ...or every fill and the ink take the nearest of these '#RRGGBB' colors
    color_mode: str = 'color'         # 'color' | 'grayscale' | 'bw' (black and white, split at `threshold`)
    threshold: int = 128              # bw: gray level 0-255 below which a pixel is black
    remove_bg: bool = False           # leave the background out (transparent pixels, else the region on most of the border)
    layout: str = 'stacked'           # 'stacked': shapes overlap and hide each other's holes (smallest files)
                                      # 'cutout': every shape has its holes cut out, nothing overlaps (cutters, editing)
    outline: OutlineParams = field(default_factory=OutlineParams)
    regions: RegionParams = field(default_factory=RegionParams)


@dataclass
class Result:
    svg: str
    regions: int
    gradients: int
    outline_paths: int
    palette: list[str] = field(default_factory=list)   # colors used, largest area first (palette modes only)


def flatten(image: Image.Image, background=(255, 255, 255)) -> Image.Image:
    """RGB copy of the image; transparent pixels are composited onto `background` (white) instead of whatever color
    the encoder left in them (often black)."""
    if image.mode in ('RGBA', 'LA', 'PA') or (image.mode == 'P' and 'transparency' in image.info):
        rgba = image.convert('RGBA')
        canvas = Image.new('RGBA', rgba.size, background + (255,))
        return Image.alpha_composite(canvas, rgba).convert('RGB')
    return image.convert('RGB')


def _alpha(image: Image.Image) -> np.ndarray | None:
    """Opacity 0..1 when the image has transparent pixels, else None."""
    if image.mode in ('RGBA', 'LA', 'PA') or (image.mode == 'P' and 'transparency' in image.info):
        a = np.asarray(image.convert('RGBA').getchannel('A'), np.float32) / 255
        return a if (a < 0.5).any() else None
    return None


def _tone(rgb: np.ndarray, mode: str, threshold: int) -> np.ndarray:
    """Grayscale, or black and white: a steep ramp around the threshold keeps the anti-aliased edge (sub-pixel
    boundaries) while every flat area becomes pure black or white."""
    if mode == 'color':
        return rgb
    g = rgb.astype(np.float32) @ np.array([0.299, 0.587, 0.114], np.float32)
    if mode == 'bw':
        g = (g - threshold) * 6.0 + 127.5
    g = np.clip(g + 0.5, 0, 255).astype(np.uint8)
    return np.repeat(g[..., None], 3, axis=2)


def _hex_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip('#')
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _kmeans(x: np.ndarray, w: np.ndarray, k: int, iters: int = 30) -> np.ndarray:
    """Area-weighted k-means in Lab; deterministic start: the largest region, then repeatedly the region that is
    both far from every chosen color and big."""
    k = min(k, len(x))
    centers = [x[int(np.argmax(w))]]
    dist = np.full(len(x), np.inf)
    for _ in range(1, k):
        dist = np.minimum(dist, np.linalg.norm(x - centers[-1], axis=1))
        centers.append(x[int(np.argmax(dist * np.sqrt(w)))])
    c = np.array(centers)
    for _ in range(iters):
        a = np.argmin(((x[:, None] - c[None]) ** 2).sum(-1), 1)
        new = np.array([np.average(x[a == j], axis=0, weights=w[a == j]) if (a == j).any() else c[j]
                        for j in range(k)])
        if np.allclose(new, c, atol=1e-3):
            break
        c = new
    return c


def _quantize(label: np.ndarray, rgb: np.ndarray, k: int, fixed: list[str] | None):
    """Give every region one palette color (k-means of the region colors, or the nearest fixed color) and merge
    touching regions that end up with the same color. Returns (label, color index per label, palette as hex)."""
    n = int(label.max())
    flat = label.ravel()
    cnt = np.bincount(flat, minlength=n + 1).astype(np.float64)
    mean = np.stack([np.bincount(flat, weights=rgb[..., c].ravel().astype(np.float64), minlength=n + 1)
                     for c in range(3)], 1) / np.maximum(cnt, 1)[:, None]
    lab = to_lab(mean[1:])
    w = cnt[1:]
    if fixed:
        centers = to_lab(np.array([_hex_rgb(h) for h in fixed], np.float32))
    else:
        centers = _kmeans(lab, w, k)
    assign = np.argmin(((lab[:, None] - centers[None]) ** 2).sum(-1), 1)
    if fixed:
        palette = list(fixed)
    else:
        palette = [to_hex(np.average(mean[1:][assign == j], axis=0, weights=w[assign == j]))
                   if (assign == j).any() else to_hex(mean[1]) for j in range(len(centers))]
    per_label = np.zeros(n + 1, np.int64)
    per_label[1:] = assign
    by_color = per_label[label]
    out = np.zeros(label.shape, np.int32)
    color_of = [0]
    for c in np.unique(assign):
        comp, m = ndimage.label(by_color == c)
        out[comp > 0] = comp[comp > 0] + (len(color_of) - 1)
        color_of += [int(c)] * m
    return out, np.array(color_of), palette


def _nearest(rgb, palette: list[str]) -> str:
    lab = to_lab(np.array([_hex_rgb(h) for h in palette], np.float32))
    return palette[int(np.argmin(np.linalg.norm(lab - to_lab(np.asarray(rgb, np.float32)), axis=1)))]


def _background(label: np.ndarray, alpha: np.ndarray | None) -> set[int]:
    """Labels to leave out for a transparent background: mostly transparent regions, or else the region that covers
    at least 40 % of the image border."""
    if alpha is not None:
        flat = label.ravel()
        cnt = np.maximum(np.bincount(flat), 1)
        opacity = np.bincount(flat, weights=alpha.ravel(), minlength=len(cnt)) / cnt
        return {int(i) for i in np.nonzero(opacity < 0.5)[0] if i > 0}
    border = np.concatenate([label[0], label[-1], label[1:-1, 0], label[1:-1, -1]])
    vals, counts = np.unique(border, return_counts=True)
    j = int(np.argmax(counts))
    return {int(vals[j])} if counts[j] >= 0.4 * len(border) else set()


def _auto_scale(w: int, h: int) -> int:
    return int(np.clip(round(4500 / max(w, h)), 1, 4))


def _safe_id(s: str) -> str:
    s = re.sub(r'[^A-Za-z0-9_-]', '-', s).strip('-') or 'v'
    return s if s[0].isalpha() else 'v' + s


def vectorize(image: Image.Image, opts: Options | None = None, executor: Executor | None = None,
              on_stage: Callable[[str, float], None] | None = None) -> Result:
    """Vectorize one image. `executor` (e.g. a ProcessPoolExecutor) optionally parallelizes curve fitting; the
    caller owns it, so one pool can be reused across images (on Windows/macOS create it under
    `if __name__ == '__main__':`). `on_stage(name, fraction)` reports progress: ink, regions, curves, svg."""
    opts = opts or Options()
    stage = on_stage or (lambda name, fraction: None)
    stage('ink', 0.05)
    alpha = _alpha(image) if opts.remove_bg else None
    rgb = _tone(np.asarray(flatten(image)), opts.color_mode, opts.threshold)
    h, w = rgb.shape[:2]
    fixed = list(opts.palette) if opts.palette else (['#000000', '#FFFFFF'] if opts.color_mode == 'bw' else None)
    quantized = bool(fixed) or bool(opts.max_colors)
    S = opts.scale or _auto_scale(w, h)
    pid = _safe_id(opts.id_prefix)

    if opts.outlines:
        ol = separate(rgb, opts.outline)
    else:
        ol = Outline(np.zeros((h, w), np.float32), np.zeros(3, np.float32), rgb.copy())
    has_ink = bool((ol.alpha > 0.5).any())
    near = ndimage.distance_transform_edt(ol.alpha < 0.5) <= opts.regions.ring_dist if has_ink else np.zeros((h, w), bool)

    stage('regions', 0.3)
    label = segment(ol.behind_rgb, near, opts.regions)
    color_of, palette, ink_hex = None, [], to_hex(ol.ink_rgb)
    if quantized:
        k = max(1, (opts.max_colors or 2) - (1 if has_ink else 0))
        label, color_of, palette = _quantize(label, ol.behind_rgb, k, fixed)
        if has_ink:
            ink_hex = _nearest(ol.ink_rgb, fixed) if fixed else ink_hex
    if opts.subpixel:
        label = refine_boundaries(label, ol.behind_rgb, ol.alpha >= 0.5 if has_ink else None)
    behind = ol.behind_rgb.astype(np.float64)
    objects = ndimage.find_objects(label)
    dropped = _background(label, alpha) if opts.remove_bg else set()
    cut = opts.layout == 'cutout' or bool(dropped)   # a removed background must not be hidden under other shapes

    # shared boundaries: every chain is fitted once and used by both regions it separates
    stage('curves', 0.65)
    chains = build_chains(label)
    tol = _corner_tolerance(ol.alpha, opts.tolerance, opts.hidden_tolerance) if has_ink else None
    if opts.subpixel:
        flat = label.ravel()
        cnt = np.maximum(np.bincount(flat), 1)
        mean_rgb = np.stack([np.bincount(flat, weights=behind[..., k].ravel()) for k in range(3)], 1) / cnt[:, None]
        hidden = ol.alpha >= 0.5 if has_ink else None
        offs = [subpixel_offsets(c, label, behind, mean_rgb, hidden) for c in chains]
    else:
        offs = [None] * len(chains)
    jobs = [(c.points, c.closed, opts.smooth, opts.tolerance if tol is None else
             tol[c.points[:, 1].astype(int), c.points[:, 0].astype(int)], 4, 55.0, o) for c, o in zip(chains, offs)]
    ochains = build_chains(outline_mask(ol.alpha, S).astype(np.int32)) if has_ink else []
    jobs += [(c.points, c.closed, opts.outline_smooth * S, opts.outline_tolerance * S, 3 * S, 60.0) for c in ochains]
    all_fit = _fit_all(jobs, executor)
    fitted, ofit = all_fit[:len(chains)], all_fit[len(chains):]
    shapes = {}
    for r, loops in region_loops(chains).items():
        areas = [loop_area(chains, lp) for lp in loops]
        k = int(np.argmax(np.abs(areas)))
        sign = np.sign(areas[k])
        outer = [lp for lp, a in zip(loops, areas) if np.sign(a) == sign]      # stacked: holes are dropped,
        shapes[r] = (abs(sum(a for a in areas if np.sign(a) == sign)),         # whatever fills them is painted
                     loops if cut else outer)                                  # on top
    order = sorted(shapes, key=lambda r: -shapes[r][0])

    stage('svg', 0.9)
    defs, fills, n_grad = [], [], 0
    rule = ' fill-rule="evenodd"' if cut else ''
    used: dict[str, float] = {}
    for i in order:
        if i in dropped:
            continue
        sl = objects[i - 1]
        sel = label[sl] == i
        ys, xs = np.nonzero(sel)
        ys = ys + sl[0].start + 0.5
        xs = xs + sl[1].start + 0.5
        colors = behind[sl][sel]
        if color_of is not None:
            fill, grad = palette[color_of[i]], ''
            used[fill] = used.get(fill, 0.0) + shapes[i][0]
        elif opts.gradients:
            fill, grad = fit_fill(ys, xs, colors, f'{pid}-g{i}', opts.regions.flat_de, opts.regions.gradient_min_area,
                                  opts.radial)
        else:
            fill, grad = to_hex(colors.mean(axis=0)), ''
        if grad:
            defs.append(grad)
            n_grad += 1
        d = compact_path(loops_to_path(shapes[i][1], fitted), decimals=opts.decimals)
        stroke = f' stroke="{fill}"' if opts.seam > 0 else ''
        fills.append(f'<path d="{d}" fill="{fill}"{rule}{stroke}/>')

    if color_of is not None and order:
        background = palette[color_of[order[0]]]
    else:
        background = to_hex(behind[label == order[0]].mean(axis=0)) if order else '#FFFFFF'
    rect = '' if cut else f'<rect width="{w}" height="{h}" fill="{background}"/>'
    seam = f' stroke-width="{opts.seam:g}" stroke-linejoin="round"' if opts.seam > 0 else ''

    outline_svg, n_out = '', 0
    if has_ink:
        loops = region_loops(ochains).get(1, [])
        n_out = len(loops)
        outline_svg = (f'<g id="outline" fill="{ink_hex}">'
                       f'<path d="{compact_path(loops_to_path(loops, ofit), 0, 0, S, opts.decimals)}"/></g>')

    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}">'
           + (f'<defs>{"".join(defs)}</defs>' if defs else '')
           + f'<g id="fill"{seam}>{rect}{"".join(fills)}</g>'
           + outline_svg + '</svg>\n')
    if quantized and has_ink:
        used[ink_hex] = used.get(ink_hex, 0.0)
    return Result(svg, len(fills), n_grad, n_out,
                  sorted(used, key=lambda c: -used[c]) if quantized else [])


def _corner_tolerance(alpha: np.ndarray, base: float, hidden: float) -> np.ndarray:
    """Allowed curve deviation at every pixel corner (h+1, w+1): `base` where the boundary is visible, growing with
    the depth inside the ink (minus a 1 px safety margin) where the outline layer will cover it anyway."""
    depth = ndimage.distance_transform_edt(alpha >= 0.5)                 # px from the nearest non-ink pixel
    corner = np.pad(depth, 1, constant_values=0)
    corner = np.minimum.reduce([corner[:-1, :-1], corner[:-1, 1:], corner[1:, :-1], corner[1:, 1:]])
    return np.clip(corner - 1.0, base, hidden)


def _fit_jobs(jobs: list) -> list:
    return [fit_chain(*j) for j in jobs]


def _fit_all(jobs: list, executor: Executor | None, min_parallel: int = 20_000) -> list:
    """Fit every chain; with an executor, in ~16 chunks of similar total length (order preserved)."""
    total = sum(len(j[0]) for j in jobs)
    if executor is None or total < min_parallel:
        return _fit_jobs(jobs)
    chunks, cur, size, target = [], [], 0, total / 16
    for j in jobs:
        cur.append(j)
        size += len(j[0])
        if size >= target:
            chunks.append(cur)
            cur, size = [], 0
    if cur:
        chunks.append(cur)
    return [f for part in executor.map(_fit_jobs, chunks) for f in part]
