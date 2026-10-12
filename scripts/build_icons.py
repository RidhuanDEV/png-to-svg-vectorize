"""Render assets/logo.svg to PNG sizes, Windows .ico and macOS .icns (needs Chrome or Edge).

    python scripts/build_icons.py
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from pngsvg.compare import find_browser  # noqa: E402

ASSETS = ROOT / 'assets'
SIZES = [16, 24, 32, 48, 64, 128, 256, 512, 1024]


def render_master(svg: Path, size: int = 1024) -> Image.Image:
    browser = find_browser()
    if not browser:
        raise SystemExit('Chrome or Edge is required to render the logo')
    with tempfile.TemporaryDirectory() as tmp:
        html = Path(tmp) / 'logo.html'
        png = Path(tmp) / 'logo.png'
        markup = svg.read_text(encoding='utf-8').replace('<svg ', f'<svg width="{size}" height="{size}" ', 1)
        html.write_text(f'<body style="margin:0;background:transparent">{markup}</body>', encoding='utf-8')
        subprocess.run([browser, '--headless=new', '--disable-gpu', '--hide-scrollbars',
                        '--default-background-color=00000000', '--force-device-scale-factor=1',
                        f'--window-size={size},{size}', f'--screenshot={png}', html.as_uri()],
                       capture_output=True, timeout=120)
        return Image.open(png).convert('RGBA')


def main() -> None:
    master = render_master(ASSETS / 'logo.svg')
    small = render_master(ASSETS / 'logo-small.svg')     # simplified mark reads better at 16-48 px
    out = ASSETS / 'icons'
    out.mkdir(parents=True, exist_ok=True)
    frames = {}
    for s in SIZES:
        src = small if s <= 48 else master
        frames[s] = src.resize((s, s), Image.LANCZOS)
        frames[s].save(out / f'icon-{s}.png', optimize=True)
    ico = [frames[s] for s in (256, 128, 64, 48, 32, 24, 16)]
    ico[0].save(out / 'icon.ico', sizes=[im.size for im in ico], append_images=ico[1:])
    master.save(out / 'icon.icns', sizes=[(s, s) for s in (16, 32, 64, 128, 256, 512, 1024)])
    print('wrote', ', '.join(sorted(p.name for p in out.iterdir())))


if __name__ == '__main__':
    main()
