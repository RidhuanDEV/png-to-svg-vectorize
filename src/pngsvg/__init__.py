"""pngsvg — turn raster cartoon illustrations into editable, library-free SVG.

Pure <path> output with linearGradient fills and crisp, sub-pixel accurate outlines.
"""
from .core import Options, Result, vectorize
from .outline import OutlineParams
from .regions import RegionParams

__all__ = ['vectorize', 'Options', 'Result', 'OutlineParams', 'RegionParams']
__version__ = '0.2.0'
