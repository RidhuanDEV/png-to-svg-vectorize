"""Named parameter sets for common kinds of artwork, so most users never touch individual parameters."""
from __future__ import annotations

from .core import Options

PRESETS = {
    'cartoon': 'cartoon / character art with ink outlines and soft shading (default)',
    'flat': 'flat illustration: solid shapes, few or no outlines, only clear gradients',
    'logo': 'logo / icon: few flat colors, crisp geometry, no gradients',
    'poster': 'photo or painting -> poster look: fewer, larger regions and smoother shapes',
}


def options_for(preset: str = 'cartoon', **overrides) -> Options:
    """Options for a named preset; keyword overrides are applied to the top-level Options fields."""
    if preset not in PRESETS:
        raise ValueError(f'unknown preset {preset!r}; choose one of: {", ".join(PRESETS)}')
    o = Options()
    if preset == 'flat':
        o.regions.flat_de = 5.0             # weak shading becomes a solid fill
        o.regions.palette_de = 5.0
        o.regions.min_area = 80
    elif preset == 'logo':
        o.gradients = False                 # (outlines stay on: line icons need the crisp ink layer)
        o.radial = False
        o.regions.palette_de = 6.0
        o.regions.merge_de = 12.0
        o.regions.min_area = 100
        o.regions.small_de = 30.0
        o.tolerance = 0.35
        o.smooth = 1.0
    elif preset == 'poster':
        o.outlines = False
        o.regions.palette_de = 6.0
        o.regions.merge_de = 12.0
        o.regions.fit_de = 5.0
        o.regions.min_area = 200
        o.regions.speckle = 40
        o.tolerance = 0.8
        o.smooth = 2.0
    for k, v in overrides.items():
        if not hasattr(o, k):
            raise AttributeError(f'Options has no field {k!r}')
        setattr(o, k, v)
    return o


def apply_overrides(o: Options, overrides: dict) -> Options:
    """Apply fine-tune overrides by their public names (app, API, profiles); nested parameters are mapped."""
    for key, value in overrides.items():
        if value is None:
            continue
        if key == 'merge_de':
            o.regions.merge_de = float(value)
        elif key == 'speckle':
            o.regions.speckle = int(value)
        elif key == 'palette':
            o.palette = tuple(value)
        elif hasattr(o, key):
            setattr(o, key, value)
        else:
            raise AttributeError(f'unknown option {key!r}')
    return o
