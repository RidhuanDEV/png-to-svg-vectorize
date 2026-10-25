# PyInstaller spec for the desktop app (onedir, windowed).  Build from the repo root:
#     pyinstaller --noconfirm packaging/pngsvg.spec
# Needs the built UI in src/pngsvg_app/static (cd app/ui && npm ci && npm run build).
import re
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH).parent
APP = 'PNG to SVG Vectorize'
VERSION = re.search(r"__version__ = '([^']+)'", (ROOT / 'src/pngsvg/__init__.py').read_text()).group(1)
STATIC = ROOT / 'src/pngsvg_app/static'
if not (STATIC / 'index.html').exists():
    raise SystemExit('UI not built: run "npm ci && npm run build" in app/ui first')

a = Analysis(
    [str(ROOT / 'packaging/launcher.py')],
    pathex=[str(ROOT / 'src')],
    datas=[(str(STATIC), 'pngsvg_app/static')],
    hiddenimports=collect_submodules('uvicorn') + ['pngsvg_app.desktop', 'pngsvg_app.server', 'pngsvg_app.jobs',
                                                   'pngsvg_app.watcher', 'pngsvg_app.svgcheck', 'pngsvg.profile'],
    excludes=['tkinter', 'matplotlib', 'IPython', 'pytest', 'PyInstaller'],
    noarchive=False,
)
pyz = PYZ(a.pure)

icon = str(ROOT / ('assets/icons/icon.icns' if sys.platform == 'darwin' else 'assets/icons/icon.ico'))
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP,
    console=False,          # windowed; --smoke reports through its exit code
    upx=False,              # UPX-packed executables trigger antivirus false positives
    icon=icon,
    version=None,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name=APP)

if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name=f'{APP}.app',
        icon=icon,
        bundle_identifier='io.github.ridhuandev.pngsvg',
        version=VERSION,
        info_plist={
            'CFBundleName': APP,
            'CFBundleDisplayName': APP,
            'CFBundleShortVersionString': VERSION,
            'CFBundleVersion': VERSION,
            'LSMinimumSystemVersion': '12.0',
            'NSHighResolutionCapable': True,
            'NSHumanReadableCopyright': '© Ridhuan Rangga Kusuma, MIT License',
        },
    )
