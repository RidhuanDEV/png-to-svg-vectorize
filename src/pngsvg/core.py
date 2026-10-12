"""Pipeline: raster cartoon illustration -> pure-path SVG (gradient fills + crisp outlines)."""
from __future__ import annotations

import re
from concurrent.futures import Executor
from dataclasses import dataclass, field

import numpy as np
from PIL import Image
from scipy import ndimage

from .color import to_hex
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
    outline: OutlineParams = field(default_factory=OutlineParams)
    regions: RegionParams = field(default_factory=RegionParams)


@dataclass
class Result:
    svg: str
    regions: int
    gradients: int
    outline_paths: int


def _auto_scale(w: int, h: int) -> int:
    return int(np.clip(round(4500 / max(w, h)), 1, 4))


def _safe_id(s: str) -> str:
    s = re.sub(r'[^A-Za-z0-9_-]', '-', s).strip('-') or 'v'
    return s if s[0].isalpha() else 'v' + s


def vectorize(image: Image.Image, opts: Options | None = None, executor: Executor | None = None) -> Result:
    """Vectorize one image. `executor` (e.g. a ProcessPoolExecutor) optionally parallelizes curve fitting; the
    caller owns it, so one pool can be reused across images (on Windows/macOS create it under
    `if __name__ == '__main__':`)."""
    opts = opts or Options()
    rgb = np.asarray(image.convert('RGB'))
    h, w = rgb.shape[:2]
    S = opts.scale or _auto_scale(w, h)
    pid = _safe_id(opts.id_prefix)

    if opts.outlines:
        ol = separate(rgb, opts.outline)
    else:
        ol = Outline(np.zeros((h, w), np.float32), np.zeros(3, np.float32), rgb.copy())
    has_ink = bool((ol.alpha > 0.5).any())
    near = ndimage.distance_transform_edt(ol.alpha < 0.5) <= opts.regions.ring_dist if has_ink else np.zeros((h, w), bool)

    label = segment(ol.behind_rgb, near, opts.regions)
    if opts.subpixel:
        label = refine_boundaries(label, ol.behind_rgb, ol.alpha >= 0.5 if has_ink else None)
    behind = ol.behind_rgb.astype(np.float64)
    objects = ndimage.find_objects(label)

    # shared boundaries: every chain is fitted once and used by both regions it separates
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
        outer = [lp for lp, a in zip(loops, areas) if np.sign(a) == sign]      # holes are dropped: whatever
        shapes[r] = (abs(sum(a for a in areas if np.sign(a) == sign)), outer)  # fills them is painted on top
    order = sorted(shapes, key=lambda r: -shapes[r][0])

    defs, fills, n_grad = [], [], 0
    for i in order:
        sl = objects[i - 1]
        sel = label[sl] == i
        ys, xs = np.nonzero(sel)
        ys = ys + sl[0].start + 0.5
        xs = xs + sl[1].start + 0.5
        colors = behind[sl][sel]
        if opts.gradients:
            fill, grad = fit_fill(ys, xs, colors, f'{pid}-g{i}', opts.regions.flat_de, opts.regions.gradient_min_area,
                                  opts.radial)
        else:
            fill, grad = to_hex(colors.mean(axis=0)), ''
        if grad:
            defs.append(grad)
            n_grad += 1
        d = compact_path(loops_to_path(shapes[i][1], fitted))
        stroke = f' stroke="{fill}"' if opts.seam > 0 else ''
        fills.append(f'<path d="{d}" fill="{fill}"{stroke}/>')

    background = to_hex(behind[label == order[0]].mean(axis=0)) if order else '#FFFFFF'
    seam = f' stroke-width="{opts.seam:g}" stroke-linejoin="round"' if opts.seam > 0 else ''

    outline_svg, n_out = '', 0
    if has_ink:
        loops = region_loops(ochains).get(1, [])
        n_out = len(loops)
        outline_svg = (f'<g id="outline" fill="{to_hex(ol.ink_rgb)}">'
                       f'<path d="{compact_path(loops_to_path(loops, ofit), 0, 0, S)}"/></g>')

    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}">'
           + (f'<defs>{"".join(defs)}</defs>' if defs else '')
           + f'<g id="fill"{seam}><rect width="{w}" height="{h}" fill="{background}"/>{"".join(fills)}</g>'
           + outline_svg + '</svg>\n')
    return Result(svg, len(order), n_grad, n_out)


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
