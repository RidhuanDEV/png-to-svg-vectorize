"""Color utilities: sRGB <-> CIE Lab, Delta E, edge-preserving smoothing, palette reduction."""
from __future__ import annotations

import numpy as np
from PIL import Image
from scipy import ndimage

_M = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]], dtype=np.float32)
_WHITE = np.array([0.95047, 1.0, 1.08883], dtype=np.float32)


def to_lab(rgb: np.ndarray) -> np.ndarray:
    """sRGB (0..255, any shape ending in 3) -> CIE Lab (D65), float32."""
    c = np.asarray(rgb, dtype=np.float32) / 255.0
    c = np.where(c > 0.04045, ((c + 0.055) / 1.055) ** 2.4, c / 12.92)
    xyz = (c @ _M.T) / _WHITE
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], axis=-1)


def delta_e(lab_a: np.ndarray, lab_b: np.ndarray) -> np.ndarray:
    """CIE76 color difference (perceptual distance; ~2.3 = just noticeable)."""
    return np.linalg.norm(np.asarray(lab_a, np.float32) - np.asarray(lab_b, np.float32), axis=-1)


def guided_filter(rgb: np.ndarray, radius: int = 8, eps: float = 0.004) -> np.ndarray:
    """Self-guided filter (He et al.), per channel: smooths soft gradients and noise, keeps hard edges."""
    img = rgb.astype(np.float32) / 255
    out = np.empty_like(img)
    k = 2 * radius + 1
    for c in range(3):
        x = img[..., c]
        mu = ndimage.uniform_filter(x, k)
        var = ndimage.uniform_filter(x * x, k) - mu * mu
        a = var / (var + eps)
        b = mu - a * mu
        out[..., c] = ndimage.uniform_filter(a, k) * x + ndimage.uniform_filter(b, k)
    return (np.clip(out, 0, 1) * 255 + 0.5).astype(np.uint8)


def reduce_palette(rgb: np.ndarray, max_colors: int = 256, merge_de: float = 3.0) -> np.ndarray:
    """Adaptive palette, then merge palette entries closer than `merge_de` into the most frequent one."""
    q = Image.fromarray(rgb).convert('P', palette=Image.Palette.ADAPTIVE, colors=max_colors)
    idx = np.asarray(q)
    pal = np.array(q.getpalette()[:max_colors * 3], dtype=np.float32).reshape(-1, 3)
    counts = np.bincount(idx.ravel(), minlength=len(pal))
    lab = to_lab(pal)
    mapping = np.arange(len(pal))
    kept: list[int] = []
    for i in np.argsort(-counts):
        if counts[i] == 0:
            continue
        for k in kept:
            if float(np.linalg.norm(lab[i] - lab[k])) < merge_de:
                mapping[i] = k
                break
        else:
            kept.append(int(i))
    return pal[mapping[idx]].astype(np.uint8)


def to_hex(rgb) -> str:
    r, g, b = (int(round(float(v))) for v in np.clip(rgb, 0, 255))
    return f'#{r:02X}{g:02X}{b:02X}'
