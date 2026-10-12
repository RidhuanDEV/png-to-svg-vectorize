"""Pipeline: raster cartoon illustration -> pure-path SVG (gradient fills + crisp outlines)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np
from PIL import Image
from scipy import ndimage

from .color import to_hex
from .outline import Outline, OutlineParams, outline_mask, separate
from .regions import RegionParams, fit_fill, segment
from .trace import compact_path, trace_mask


@dataclass
class Options:
    scale: int | None = None          # tracing upscale; None = auto (long side ~4500 px)
    outlines: bool = True             # separate ink outlines into their own crisp layer
    gradients: bool = True            # gradient fills (False = flat colors)
    overlap: int = 2                  # px (at tracing scale) each region grows so neighbours never show seams
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
    area = np.bincount(label.ravel())
    order = sorted((i for i in range(1, len(objects) + 1) if objects[i - 1] is not None), key=lambda i: -area[i])

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
        mask = _upsample_mask(sel, S, opts.overlap)
        for d in trace_mask(mask, speckle=S * 3):
            fills.append((d, sl[1].start * S, sl[0].start * S, fill))

    background = to_hex(behind[label == order[0]].mean(axis=0)) if order else '#FFFFFF'
    fill_svg = ''.join(f'<path d="{compact_path(d, ox, oy, S)}" fill="{f}"/>' for d, ox, oy, f in fills)

    outline_svg, n_out = '', 0
    if has_ink:
        om = outline_mask(ol.alpha, S)
        paths = trace_mask(om, speckle=S * 4)
        n_out = len(paths)
        outline_svg = (f'<g id="outline" fill="{to_hex(ol.ink_rgb)}">'
                       + ''.join(f'<path d="{compact_path(d, 0, 0, S)}"/>' for d in paths) + '</g>')

    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}">'
           + (f'<defs>{"".join(defs)}</defs>' if defs else '')
           + f'<g id="fill"><rect width="{w}" height="{h}" fill="{background}"/>{fill_svg}</g>'
           + outline_svg + '</svg>\n')
    return Result(svg, len(order), n_grad, n_out)


def _upsample_mask(mask: np.ndarray, scale: int, overlap: int) -> np.ndarray:
    h, w = mask.shape
    big = np.asarray(Image.fromarray(mask.astype(np.uint8) * 255).resize((w * scale, h * scale), Image.BILINEAR),
                     dtype=np.float32) / 255
    big = ndimage.gaussian_filter(big, sigma=scale * 0.7) > 0.5
    return ndimage.binary_dilation(big, iterations=overlap) if overlap else big
