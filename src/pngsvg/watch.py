"""Watch folder: pictures that appear in a folder are converted into another folder (PNG in -> SVG/PDF/... out).

`NewFiles` finds pictures added after watching started, once their size has stopped changing (still being copied
otherwise). The command line (`png2svg watch IN OUT`) and the desktop app both use it.
"""
from __future__ import annotations

from pathlib import Path

IMAGE_SUFFIXES = ('.png', '.jpg', '.jpeg', '.webp')


class NewFiles:
    """Pictures added to `folder` since creation, each reported once, when its size was the same on two polls."""

    def __init__(self, folder: Path, include_existing: bool = False):
        self.folder = Path(folder)
        self._done: set[str] = set() if include_existing else {p.name for p in self._pictures()}
        self._sizes: dict[str, int] = {}

    def _pictures(self) -> list[Path]:
        try:
            return sorted(p for p in self.folder.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES)
        except OSError:
            return []

    def poll(self) -> list[Path]:
        ready = []
        for p in self._pictures():
            if p.name in self._done:
                continue
            try:
                size = p.stat().st_size
            except OSError:
                continue
            if size > 0 and self._sizes.get(p.name) == size:
                self._done.add(p.name)
                self._sizes.pop(p.name, None)
                ready.append(p)
            else:
                self._sizes[p.name] = size
        return ready


def unique_path(folder: Path, filename: str) -> Path:
    """`folder/filename`, or name-2.ext, name-3.ext, ... so an existing file is never overwritten."""
    stem, dot, ext = filename.rpartition('.')
    path, k = folder / filename, 1
    while path.exists():
        k += 1
        path = folder / (f'{stem}-{k}.{ext}' if dot else f'{filename}-{k}')
    return path
