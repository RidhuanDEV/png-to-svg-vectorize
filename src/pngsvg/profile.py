"""Style profiles: a preset plus option overrides saved as `<name>.pngsvg-profile.json`, shared by the app and the CLI.

    {"format": "pngsvg-profile", "version": 1, "name": "Brand logo", "preset": "logo",
     "options": {"max_colors": 4, "remove_bg": true}}

Options use the same names and ranges as the app's fine-tune panel (and the service API); anything else is rejected.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .presets import PRESETS

FORMAT = 'pngsvg-profile'
SUFFIX = '.pngsvg-profile.json'
_HEX = re.compile(r'^#[0-9A-Fa-f]{6}$')

# name: (type, min, max) or (type, choices)
OPTIONS: dict[str, tuple] = {
    'outlines': (bool,), 'gradients': (bool,), 'radial': (bool,), 'remove_bg': (bool,), 'layers': (bool,),
    'tolerance': (float, 0.1, 3.0), 'smooth': (float, 0.0, 5.0), 'merge_de': (float, 1.0, 30.0),
    'seam': (float, 0.0, 2.0), 'scale': (int, 1, 4), 'decimals': (int, 0, 3), 'max_colors': (int, 2, 64),
    'threshold': (int, 1, 254), 'speckle': (int, 0, 5000),
    'color_mode': (str, ('color', 'grayscale', 'bw')), 'layout': (str, ('stacked', 'cutout', 'centerline')),
    'palette': (list,),
}


class ProfileError(ValueError):
    pass


def check_options(options: dict[str, Any]) -> dict[str, Any]:
    """Validated copy of option overrides (None values dropped)."""
    if not isinstance(options, dict):
        raise ProfileError('options must be an object')
    out: dict[str, Any] = {}
    for key, value in options.items():
        if value is None:
            continue
        spec = OPTIONS.get(key)
        if spec is None:
            raise ProfileError(f'unknown option {key!r}')
        kind = spec[0]
        if kind is bool:
            if not isinstance(value, bool):
                raise ProfileError(f'{key} must be true or false')
        elif kind in (int, float):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or (kind is int and value != int(value)):
                raise ProfileError(f'{key} must be a{"n integer" if kind is int else " number"}')
            if not spec[1] <= value <= spec[2]:
                raise ProfileError(f'{key} must be between {spec[1]} and {spec[2]}')
            value = kind(value)
        elif kind is str:
            if value not in spec[1]:
                raise ProfileError(f'{key} must be one of: {", ".join(spec[1])}')
        else:
            if not isinstance(value, list) or not 1 <= len(value) <= 64 or \
                    not all(isinstance(c, str) and _HEX.match(c) for c in value):
                raise ProfileError('palette must be a list of 1-64 colors like "#1A2B3C"')
            value = [c.upper() for c in value]
        out[key] = value
    return out


def parse(data: Any) -> tuple[str, dict[str, Any], str]:
    """(preset, options, name) from a decoded profile."""
    if not isinstance(data, dict) or data.get('format') != FORMAT:
        raise ProfileError('not a style profile (format must be "pngsvg-profile")')
    if data.get('version') != 1:
        raise ProfileError('unsupported profile version')
    preset = data.get('preset', 'cartoon')
    if preset not in PRESETS:
        raise ProfileError(f'unknown preset {preset!r}')
    name = data.get('name', '')
    if not isinstance(name, str) or len(name) > 80:
        raise ProfileError('name must be text of at most 80 characters')
    return preset, check_options(data.get('options', {})), name


def load(path: str | Path) -> tuple[str, dict[str, Any], str]:
    p = Path(path)
    if p.stat().st_size > 64 * 1024:
        raise ProfileError('profile file too large')
    try:
        data = json.loads(p.read_text(encoding='utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise ProfileError(f'not valid JSON: {e}') from None
    return parse(data)


def dump(preset: str, options: dict[str, Any], name: str = '') -> str:
    parse({'format': FORMAT, 'version': 1, 'name': name, 'preset': preset, 'options': options})   # validate
    return json.dumps({'format': FORMAT, 'version': 1, 'name': name, 'preset': preset,
                       'options': check_options(options)}, indent=2, ensure_ascii=False) + '\n'
