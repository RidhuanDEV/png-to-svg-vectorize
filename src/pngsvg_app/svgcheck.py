"""Validation of an SVG edited in the page (recolor / delete / merge shapes) before it replaces a result.

Only the subset the engine writes is accepted: the same elements and presentation attributes, local gradient
references, and the original viewBox. No scripts, styles, links, external references, entities or foreign markup can
get into a saved file or an export.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET

NS = '{http://www.w3.org/2000/svg}'
MAX_BYTES = 64 * 1024 * 1024

ATTRS = {
    'svg': {'viewBox', 'width', 'height'},
    'title': set(),
    'defs': set(),
    'g': {'id', 'class', 'fill', 'stroke', 'stroke-width', 'stroke-linejoin', 'stroke-linecap', 'display'},
    'path': {'id', 'class', 'd', 'fill', 'fill-rule', 'stroke', 'stroke-width'},
    'rect': {'width', 'height', 'x', 'y', 'fill'},
    'linearGradient': {'id', 'gradientUnits', 'x1', 'y1', 'x2', 'y2'},
    'radialGradient': {'id', 'gradientUnits', 'cx', 'cy', 'r', 'gradientTransform'},
    'stop': {'offset', 'stop-color'},
}
_PAINT = re.compile(r'^(none|#[0-9A-Fa-f]{6}|url\(#[A-Za-z][\w-]{0,80}\))$')
_NUMBERS = re.compile(r'^[-+0-9.eE ,]*$')
_PATH = re.compile(r'^[MLCQZHVmlcqzhv0-9.eE ,+-]*$')
_ID = re.compile(r'^[A-Za-z][\w-]{0,80}$')
_MATRIX = re.compile(r'^matrix\([-+0-9.eE ,]+\)$')
_ENUM = {
    'fill-rule': {'evenodd', 'nonzero'}, 'stroke-linejoin': {'round', 'miter', 'bevel'},
    'stroke-linecap': {'round', 'butt', 'square'}, 'display': {'none'}, 'gradientUnits': {'userSpaceOnUse'},
}


class EditError(ValueError):
    pass


def _check_value(tag: str, name: str, value: str) -> None:
    if name in ('fill', 'stroke', 'stop-color'):
        ok = bool(_PAINT.match(value)) and not (name == 'stop-color' and not value.startswith('#'))
    elif name == 'd':
        ok = bool(_PATH.match(value))
    elif name in ('id', 'class'):
        ok = bool(_ID.match(value))
    elif name == 'gradientTransform':
        ok = bool(_MATRIX.match(value))
    elif name in _ENUM:
        ok = value in _ENUM[name]
    else:
        ok = bool(_NUMBERS.match(value)) and len(value) < 64
    if not ok:
        raise EditError(f'value not allowed: {tag} {name}')


def check_edited_svg(text: str, original: str) -> str:
    """The edited SVG, normalized (one line, engine style), or EditError."""
    if len(text.encode('utf-8')) > MAX_BYTES:
        raise EditError('edited SVG too large')
    if re.search(r'<!(DOCTYPE|ENTITY)|<\?(?!xml\s)', text, re.I):
        raise EditError('declarations are not allowed')
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        raise EditError(f'not well-formed: {e}') from None
    if root.tag != NS + 'svg':
        raise EditError('not an SVG document')
    vb = re.search(r'viewBox="([^"]+)"', original)
    if vb is None or root.get('viewBox') != vb.group(1):
        raise EditError('the picture size cannot change')
    ids: set[str] = set()
    refs: set[str] = set()
    for el in root.iter():
        if not isinstance(el.tag, str) or not el.tag.startswith(NS):
            raise EditError('foreign markup is not allowed')
        tag = el.tag[len(NS):]
        allowed = ATTRS.get(tag)
        if allowed is None:
            raise EditError(f'element not allowed: {tag}')
        if (tag != 'title' and (el.text or '').strip()) or (el.tail or '').strip():
            raise EditError('text content is not allowed')
        if tag == 'title' and len(el) > 0:
            raise EditError('a title holds text only')
        for name, value in el.attrib.items():
            if name not in allowed:
                raise EditError(f'attribute not allowed: {tag} {name}')
            _check_value(tag, name, value)
            if name == 'id':
                ids.add(value)
            ref = re.match(r'url\(#(.+)\)$', value)
            if ref:
                refs.add(ref.group(1))
    if not refs <= ids:
        raise EditError('a fill refers to a missing gradient')
    for size in ('width', 'height'):          # the saved size follows Settings, as for unedited results
        root.attrib.pop(size, None)
    ET.register_namespace('', NS[1:-1])
    return ET.tostring(root, encoding='unicode', short_empty_elements=True) + '\n'
