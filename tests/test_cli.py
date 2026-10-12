"""Command line, run as a real subprocess (spawned worker processes must be able to import the worker function)."""
import subprocess
import sys

from PIL import Image, ImageDraw


def _image(path, color):
    img = Image.new('RGB', (120, 90), (240, 244, 250))
    ImageDraw.Draw(img).ellipse((15, 10, 85, 80), fill=color, outline=(15, 23, 42), width=3)
    img.save(path)


def test_python_m_batch_with_worker_processes(tmp_path):
    a, b = tmp_path / 'a.png', tmp_path / 'b.png'
    _image(a, (37, 99, 235))
    _image(b, (245, 158, 11))
    out = tmp_path / 'out'
    run = subprocess.run([sys.executable, '-m', 'pngsvg', str(a), str(b), '-o', str(out), '-j', '2'],
                         capture_output=True, text=True, timeout=300)
    assert run.returncode == 0, run.stderr
    assert (out / 'a.svg').read_text(encoding='utf-8').startswith('<svg')
    assert (out / 'b.svg').read_text(encoding='utf-8').startswith('<svg')


def test_single_file_with_preset(tmp_path):
    a = tmp_path / 'logo.png'
    _image(a, (37, 99, 235))
    run = subprocess.run([sys.executable, '-m', 'pngsvg', str(a), '-p', 'logo', '-j', '1'],
                         capture_output=True, text=True, timeout=300)
    assert run.returncode == 0, run.stderr
    assert '<linearGradient' not in (tmp_path / 'logo.svg').read_text(encoding='utf-8')
