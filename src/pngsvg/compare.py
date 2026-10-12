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


def render(svg_text: str, width: int, height: int) -> Image.Image | None:
    browser = find_browser()
    if not browser:
        return None
    with tempfile.TemporaryDirectory() as tmp:
        html = Path(tmp) / 'r.html'
        png = Path(tmp) / 'r.png'
        sized = svg_text.replace('<svg ', f'<svg width="{width}" height="{height}" ', 1)
        html.write_text(f'<body style="margin:0;overflow:hidden">{sized}</body>', encoding='utf-8')
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
