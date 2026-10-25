"""pngsvg — turn raster cartoon illustrations into editable, library-free SVG.

Pure <path> output with linear/radial gradient fills and crisp, sub-pixel accurate outlines.
"""
from .core import Options, Result, vectorize
from .outline import OutlineParams
from .presets import PRESETS, options_for
from .regions import RegionParams

__all__ = ['vectorize', 'Options', 'Result', 'OutlineParams', 'RegionParams', 'PRESETS', 'options_for']
__version__ = '1.3.0'
