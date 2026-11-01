"""Optional quality check: render an SVG with a headless Chromium browser and compare it with the source."""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

_CANDIDATES = [
    os.environ.get('PNGSVG_CHROME', ''),
    r'C:\Program Files\Google\Chrome\Application\chrome.exe',
    r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
]


def find_browser() -> str | None:
    for c in _CANDIDATES:
        if c and Path(c).exists():
            return c
    for name in ('google-chrome', 'chromium', 'chromium-browser', 'chrome', 'msedge'):
        p = shutil.which(name)
        if p:
            return p
    return None


def render(svg_text: str, width: int, height: int, background: str = '#fff') -> Image.Image | None:
    """The SVG as Chrome/Edge draws it at width x height, on `background` (a CSS background: a checkerboard shows
    what is transparent)."""
    browser = find_browser()
    if not browser:
        return None
    with tempfile.TemporaryDirectory() as tmp:
        html = Path(tmp) / 'r.html'
        png = Path(tmp) / 'r.png'
        sized = svg_text.replace('<svg ', f'<svg width="{width}" height="{height}" ', 1)
        html.write_text(f'<body style="margin:0;overflow:hidden;background:{background}">{sized}</body>', encoding='utf-8')
        subprocess.run([browser, '--headless=new', '--disable-gpu', '--hide-scrollbars', '--force-device-scale-factor=1',
                        f'--window-size={width},{height}', f'--screenshot={png}', html.as_uri()],
                       capture_output=True, timeout=180)
        return Image.open(png).convert('RGB') if png.exists() else None


def similarity(a: Image.Image, b: Image.Image) -> tuple[float, float]:
    """(100 - mean abs error %, % pixels whose max channel error <= 24/255)."""
    x = np.asarray(a.convert('RGB'), dtype=np.int16)
    y = np.asarray(b.convert('RGB').resize(a.size), dtype=np.int16)
    d = np.abs(x - y)
    return 100 * (1 - d.mean() / 255), 100 * float((d.max(axis=2) <= 24).mean())


def psnr(a: Image.Image, b: Image.Image) -> float:
    """Peak signal-to-noise ratio over RGB in dB (inf when identical)."""
    x = np.asarray(a.convert('RGB'), dtype=np.float64)
    y = np.asarray(b.convert('RGB').resize(a.size), dtype=np.float64)
    mse = float(((x - y) ** 2).mean())
    return float('inf') if mse == 0 else 10 * np.log10(255 ** 2 / mse)


def ssim(a: Image.Image, b: Image.Image) -> float:
    """Mean structural similarity (Wang et al. 2004) of the luma: Gaussian window sigma 1.5, K1 0.01, K2 0.03."""
    from scipy.ndimage import gaussian_filter

    def luma(im: Image.Image) -> np.ndarray:
        return np.asarray(im.convert('RGB'), dtype=np.float64) @ np.array([0.299, 0.587, 0.114])

    x, y = luma(a), luma(b.resize(a.size))
    c1, c2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    mx, my = gaussian_filter(x, 1.5), gaussian_filter(y, 1.5)
    vx = gaussian_filter(x * x, 1.5) - mx * mx
    vy = gaussian_filter(y * y, 1.5) - my * my
    cov = gaussian_filter(x * y, 1.5) - mx * my
    s = ((2 * mx * my + c1) * (2 * cov + c2)) / ((mx * mx + my * my + c1) * (vx + vy + c2))
    return float(s.mean())


def edge_split(a: Image.Image, b: Image.Image, band: int = 1) -> tuple[float, float]:
    """Similarity (as `similarity`) away from color edges and share of the total error on them: edge pixels are
    those within `band` px of a source pixel whose neighbour differs by more than 24/255 (anti-aliasing)."""
    from scipy.ndimage import binary_dilation

    x = np.asarray(a.convert('RGB'), dtype=np.int16)
    y = np.asarray(b.convert('RGB').resize(a.size), dtype=np.int16)
    edge = np.zeros(x.shape[:2], bool)
    for axis in (0, 1):
        jump = np.abs(np.diff(x, axis=axis)).max(-1) > 24
        pad = [(0, 0), (0, 0)]
        pad[axis] = (0, 1)
        edge |= np.pad(jump, pad)
        pad[axis] = (1, 0)
        edge |= np.pad(jump, pad)
    if band > 1:
        edge = binary_dilation(edge, iterations=band - 1)
    err = np.abs(x - y).sum(-1)
    total = float(err.sum())
    flat = 100 * (1 - err[~edge].mean() / 3 / 255) if (~edge).any() else 100.0
    return flat, (100 * float(err[edge].sum()) / total if total else 0.0)


def defect_map(a: Image.Image, b: Image.Image, de: float = 5.0) -> np.ndarray:
    """Where the two pictures visibly differ: CIEDE2000 above `de` (5 = clearly visible side by side), after a 3x3
    opening that drops the 1-2 px lines along edges (anti-aliasing that never matches exactly). Bool (h, w)."""
    from scipy.ndimage import binary_opening

    from .color import delta_e2000, to_lab

    x = to_lab(np.asarray(a.convert('RGB'), dtype=np.float64)).astype(np.float64)
    y = to_lab(np.asarray(b.convert('RGB').resize(a.size), dtype=np.float64)).astype(np.float64)
    return binary_opening(delta_e2000(x, y) > de, structure=np.ones((3, 3), bool))


def defect_area(a: Image.Image, b: Image.Image, de: float = 5.0) -> float:
    """Share (%) of the picture covered by visible defects (see `defect_map`): a lost color, a missing shape, a
    wrong gradient. Mean-error scores hide these because they cover few pixels."""
    return 100 * float(defect_map(a, b, de).mean())
