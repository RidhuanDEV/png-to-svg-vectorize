"""Pipeline: raster cartoon illustration -> pure-path SVG (gradient fills + crisp outlines)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np
from PIL import Image
from scipy import ndimage

from .color import to_hex
from .curves import fit_chain
from .outline import Outline, OutlineParams, outline_mask, separate
from .planar import build_chains, loop_area, loops_to_path, region_loops
from .regions import RegionParams, fit_fill, segment
from .pathdata import compact_path


@dataclass
class Options:
    scale: int | None = None          # tracing upscale; None = auto (long side ~4500 px)
    outlines: bool = True             # separate ink outlines into their own crisp layer
    gradients: bool = True            # gradient fills (False = flat colors)
    smooth: float = 1.5               # fill boundary smoothing along the curve (sigma, source px)
    tolerance: float = 0.5            # max Bezier deviation from the smoothed fill boundary (source px)
    hidden_tolerance: float = 3.0     # ...where a fill boundary lies under the outline layer (invisible), up to this
    outline_smooth: float = 0.5       # the outline is already sub-pixel smooth: lighter smoothing keeps line tips
    outline_tolerance: float = 0.35
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


def vectorize(image: Image.Image, opts: Options | None = None) -> Result:
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
    behind = ol.behind_rgb.astype(np.float64)
    objects = ndimage.find_objects(label)

    # shared boundaries: every chain is fitted once and used by both regions it separates
    chains = build_chains(label)
    tol = _corner_tolerance(ol.alpha, opts.tolerance, opts.hidden_tolerance) if has_ink else None
    fitted = [fit_chain(c.points, c.closed, opts.smooth, opts.tolerance if tol is None else
                        tol[c.points[:, 1].astype(int), c.points[:, 0].astype(int)]) for c in chains]
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
            fill, grad = fit_fill(ys, xs, colors, f'{pid}-g{i}', opts.regions.flat_de, opts.regions.gradient_min_area)
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
        om = outline_mask(ol.alpha, S).astype(np.int32)
        ochains = build_chains(om)
        ofit = [fit_chain(c.points, c.closed, opts.outline_smooth * S, opts.outline_tolerance * S, window=3 * S,
                          corner_deg=60.0) for c in ochains]
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
