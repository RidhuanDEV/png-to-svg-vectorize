"""Optional AI enhancement before vectorizing: a Real-ESRGAN model (ONNX) cleans and enlarges the picture so the
tracer sees crisp, artifact-free edges. Entirely local; needs the optional `onnxruntime` package (DirectML on
Windows, CoreML on macOS, CPU everywhere) and a model file (downloaded once by the app, see pngsvg_app.models).

The vectorizer itself does not change: it simply receives the enhanced image.
"""
from __future__ import annotations

import threading
from pathlib import Path

import numpy as np
from PIL import Image

ACCELS = ('auto', 'gpu', 'cpu')
_GPU = ('DmlExecutionProvider', 'CoreMLExecutionProvider', 'CUDAExecutionProvider')


def runtime_available() -> bool:
    try:
        import onnxruntime  # noqa: F401
    except Exception:  # noqa: BLE001 - missing wheel (e.g. macOS Intel) or broken install
        return False
    return True


def gpu_providers() -> list[str]:
    if not runtime_available():
        return []
    import onnxruntime as ort
    return [p for p in ort.get_available_providers() if p in _GPU]


def providers_for(accel: str) -> list[str]:
    """Execution providers in preference order; CPU is always the last resort."""
    gpu = gpu_providers() if accel in ('auto', 'gpu') else []
    return gpu + ['CPUExecutionProvider']


_sessions: dict[tuple[str, tuple[str, ...]], object] = {}
_lock = threading.Lock()


def _session(model: Path, providers: list[str]):
    import onnxruntime as ort
    key = (str(model), tuple(providers))
    with _lock:
        sess = _sessions.get(key)
        if sess is None:
            opts = ort.SessionOptions()
            opts.log_severity_level = 3
            try:
                sess = ort.InferenceSession(str(model), sess_options=opts, providers=providers)
            except Exception:  # noqa: BLE001 - a GPU provider can fail on some drivers: fall back to CPU
                sess = ort.InferenceSession(str(model), sess_options=opts, providers=['CPUExecutionProvider'])
            _sessions[key] = sess
        return sess


def upscale(image: Image.Image, model: Path, accel: str = 'auto', tile: int = 192, overlap: int = 12,
            scale: int = 4) -> Image.Image:
    """Run the x`scale` model over the image in overlapping tiles (bounded memory for any image size)."""
    rgb = np.asarray(image.convert('RGB'), dtype=np.float32) / 255.0
    h, w = rgb.shape[:2]
    sess = _session(model, providers_for(accel))
    out = np.zeros((h * scale, w * scale, 3), dtype=np.float32)
    step = tile - 2 * overlap
    for y0 in range(0, h, step):
        for x0 in range(0, w, step):
            # input window with context on every side, clipped to the image
            ya, yb = max(0, y0 - overlap), min(h, y0 + step + overlap)
            xa, xb = max(0, x0 - overlap), min(w, x0 + step + overlap)
            patch = rgb[ya:yb, xa:xb].transpose(2, 0, 1)[None]
            res = sess.run(None, {'input': np.ascontiguousarray(patch)})[0][0].transpose(1, 2, 0)
            # keep only the centre (the part without the context margins)
            cy0, cx0 = (y0 - ya) * scale, (x0 - xa) * scale
            ch = (min(h, y0 + step) - y0) * scale
            cw = (min(w, x0 + step) - x0) * scale
            out[y0 * scale:y0 * scale + ch, x0 * scale:x0 * scale + cw] = res[cy0:cy0 + ch, cx0:cx0 + cw]
    return Image.fromarray(np.clip(out * 255.0 + 0.5, 0, 255).astype(np.uint8))


def enhance(image: Image.Image, model: Path, accel: str = 'auto', target: int = 2) -> Image.Image:
    """AI-cleaned copy at `target` × the original size (the model works at x4; the result is resized down)."""
    up = upscale(image, model, accel)
    w, h = image.size
    if target == 4:
        return up
    return up.resize((w * target, h * target), Image.Resampling.LANCZOS)
