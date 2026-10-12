"""Procedural benchmark images (license-free, reproducible). Each targets a known difficulty.

    python bench/synthetic.py            # writes bench/images/*.png
Everything is drawn at 4x and downsampled (anti-aliased like real artwork); some images get a slight blur and
noise to mimic image-generator output.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

OUT = Path(__file__).resolve().parent / 'images'
W, H, K = 1024, 768, 4          # output size, supersampling factor
INK = (16, 30, 46)


def canvas(bg):
    return Image.new('RGB', (W * K, H * K), bg)


def finish(img: Image.Image, soft: float = 0.0, noise: float = 0.0, seed: int = 0) -> Image.Image:
    out = img.resize((W, H), Image.LANCZOS)
    if soft:
        out = out.filter(ImageFilter.GaussianBlur(soft))
    if noise:
        a = np.asarray(out).astype(np.float32)
        a += np.random.default_rng(seed).normal(0, noise, a.shape)
        out = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    return out


def lin_gradient(size, c0, c1, angle_deg):
    w, h = size
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    a = math.radians(angle_deg)
    t = (xx * math.cos(a) + yy * math.sin(a))
    t = (t - t.min()) / max(t.max() - t.min(), 1)
    c = np.array(c0, np.float32) * (1 - t[..., None]) + np.array(c1, np.float32) * t[..., None]
    return Image.fromarray(c.astype(np.uint8))


def radial_gradient(size, c_in, c_out, cx, cy, r):
    w, h = size
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    t = np.clip(np.hypot(xx - cx, yy - cy) / r, 0, 1)[..., None]
    c = np.array(c_in, np.float32) * (1 - t) + np.array(c_out, np.float32) * t
    return Image.fromarray(c.astype(np.uint8))


def paste_masked(img, fill_img, draw_mask):
    m = Image.new('L', img.size, 0)
    draw_mask(ImageDraw.Draw(m))
    img.paste(fill_img, (0, 0), m)


def s(*v):
    return [x * K for x in v]


def face():
    img = canvas((214, 238, 226))
    d = ImageDraw.Draw(img)
    d.ellipse(s(250, 150, 770, 760), fill=(32, 46, 62))                         # hair mass
    skin = lin_gradient(img.size, (255, 214, 168), (226, 160, 112), 20)
    paste_masked(img, skin, lambda m: m.ellipse(s(300, 180, 720, 700), fill=255))
    blush = Image.new('L', img.size, 0)
    ImageDraw.Draw(blush).ellipse(s(350, 470, 450, 530), fill=150)
    ImageDraw.Draw(blush).ellipse(s(570, 470, 670, 530), fill=150)
    blush = blush.filter(ImageFilter.GaussianBlur(14 * K))
    img.paste(Image.new('RGB', img.size, (240, 140, 130)), (0, 0), blush)
    d = ImageDraw.Draw(img)
    d.ellipse(s(300, 180, 720, 700), outline=INK, width=9 * K)
    for x in (410, 610):
        d.ellipse(s(x - 26, 360, x + 26, 420), fill=INK)
        d.ellipse(s(x - 12, 372, x - 2, 384), fill=(255, 255, 255))
        d.arc(s(x - 50, 300, x + 50, 360), 200, 340, fill=INK, width=8 * K)
    d.chord(s(420, 520, 600, 640), 0, 180, fill=(150, 40, 50), outline=INK, width=7 * K)
    d.rectangle(s(440, 580, 580, 596), fill=(250, 250, 250))
    d.line(s(512, 440, 500, 490, 520, 492), fill=(200, 110, 70), width=6 * K)
    return finish(img, soft=0.6, noise=2.0, seed=1)


def logo_flat():
    img = canvas((250, 250, 248))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(s(120, 140, 480, 500), radius=60 * K, fill=(79, 70, 229))
    d.ellipse(s(380, 260, 700, 580), fill=(14, 165, 164))
    d.polygon(s(620, 180, 900, 620, 520, 620), fill=(245, 158, 11))
    d.rounded_rectangle(s(160, 560, 860, 640), radius=40 * K, fill=(30, 41, 59))
    return finish(img)


def icon_outline():
    img = canvas((255, 255, 255))
    d = ImageDraw.Draw(img)
    d.polygon(s(512, 120, 820, 380, 204, 380), fill=(239, 68, 68), outline=INK)
    d.rectangle(s(260, 380, 764, 680), fill=(254, 243, 199))
    d.rectangle(s(450, 500, 574, 680), fill=(146, 64, 14))
    d.rectangle(s(310, 430, 410, 520), fill=(147, 197, 253))
    d.rectangle(s(614, 430, 714, 520), fill=(147, 197, 253))
    for box in ((260, 380, 764, 680), (450, 500, 574, 680), (310, 430, 410, 520), (614, 430, 714, 520)):
        d.rectangle(s(*box), outline=INK, width=10 * K)
    d.line(s(204, 380, 512, 120, 820, 380, 204, 380), fill=INK, width=10 * K, joint='curve')
    return finish(img)


def sphere():
    img = canvas((236, 242, 252))
    ball = radial_gradient(img.size, (186, 230, 253), (37, 99, 235), 430 * K, 300 * K, 330 * K)
    paste_masked(img, ball, lambda m: m.ellipse(s(282, 154, 742, 614), fill=255))
    shadow = Image.new('L', img.size, 0)
    ImageDraw.Draw(shadow).ellipse(s(330, 640, 700, 700), fill=120)
    img.paste(Image.new('RGB', img.size, (120, 130, 150)), (0, 0), shadow.filter(ImageFilter.GaussianBlur(10 * K)))
    ImageDraw.Draw(img).ellipse(s(282, 154, 742, 614), outline=INK, width=8 * K)
    return finish(img, soft=0.5)


def rings():
    img = canvas((198, 240, 226))
    d = ImageDraw.Draw(img)
    for r in (360, 290, 220):
        d.ellipse(s(512 - r, 384 - r, 512 + r, 384 + r), outline=(160, 225, 206), width=34 * K)
    d.rounded_rectangle(s(400, 250, 624, 560), radius=40 * K, fill=(34, 160, 110), outline=INK, width=8 * K)
    return finish(img, soft=1.2, noise=1.5, seed=2)


def stripes():
    img = canvas((255, 247, 237))
    d = ImageDraw.Draw(img)
    d.rectangle(s(160, 140, 860, 640), fill=(194, 65, 12))
    for i, x in enumerate(range(180, 860, 46)):
        d.rectangle(s(x, 150, x + 20, 630), fill=(251, 191, 36) if i % 2 else (254, 215, 170))
    for y in range(190, 620, 70):
        for x in range(205, 840, 70):
            d.ellipse(s(x - 9, y - 9, x + 9, y + 9), fill=(120, 53, 15))
    d.rectangle(s(160, 140, 860, 640), outline=INK, width=8 * K)
    return finish(img, soft=0.4)


def thin_lines():
    img = canvas((255, 255, 255))
    d = ImageDraw.Draw(img)
    for i in range(14):
        a = i / 14 * math.pi
        d.line(s(512, 384, 512 + 300 * math.cos(a), 384 - 300 * math.sin(a)), fill=INK, width=int(1.6 * K))
    d.arc(s(212, 84, 812, 684), 180, 360, fill=INK, width=2 * K)
    d.arc(s(312, 184, 712, 584), 180, 360, fill=INK, width=3 * K)
    for x in range(160, 880, 36):
        d.line(s(x, 520, x + 18, 700), fill=(80, 90, 110), width=int(1.2 * K))
    return finish(img)


def gradient_bg():
    img = lin_gradient((W * K, H * K), (255, 237, 213), (253, 186, 116), 70)
    d = ImageDraw.Draw(img)
    d.ellipse(s(140, 200, 440, 500), fill=(124, 58, 237), outline=INK, width=8 * K)
    d.rounded_rectangle(s(540, 220, 880, 560), radius=70 * K, fill=(16, 185, 129), outline=INK, width=8 * K)
    return finish(img, soft=0.5, noise=1.0, seed=3)


def leaves():
    img = canvas((236, 253, 245))
    rng = np.random.default_rng(7)
    for i in range(9):
        cx, cy = rng.uniform(150, 870), rng.uniform(120, 650)
        w, h = rng.uniform(90, 200), rng.uniform(50, 110)
        ang = rng.uniform(0, 180)
        leaf = Image.new('L', (int(w * 2 * K), int(h * 2 * K)), 0)
        ImageDraw.Draw(leaf).ellipse([0, 0, leaf.size[0] - 1, leaf.size[1] - 1], fill=255)
        leaf = leaf.rotate(ang, expand=True)
        fill = lin_gradient(leaf.size, (134, 239, 172), (21, 128, 61), ang + 90)
        x0, y0 = int(cx * K - leaf.size[0] / 2), int(cy * K - leaf.size[1] / 2)
        edge = leaf.filter(ImageFilter.MaxFilter(13))          # ~3 px ink outline after downsampling
        img.paste(Image.new('RGB', leaf.size, INK), (x0, y0), edge)
        img.paste(fill, (x0, y0), leaf)
    return finish(img, soft=0.6, noise=1.5, seed=4)


def badge():
    img = canvas((255, 255, 255))
    d = ImageDraw.Draw(img)
    d.ellipse(s(262, 134, 762, 634), fill=(220, 38, 38))
    d.ellipse(s(302, 174, 722, 594), fill=(254, 242, 242))
    pts = []
    for i in range(10):
        a = math.pi / 2 + i * math.pi / 5
        r = 170 if i % 2 == 0 else 70
        pts += [512 + r * math.cos(a), 384 - r * math.sin(a)]
    d.polygon(s(*pts), fill=(234, 179, 8))
    d.rounded_rectangle(s(372, 600, 652, 690), radius=20 * K, fill=(30, 64, 175))
    return finish(img)


def line_icon():
    img = canvas((248, 250, 252))
    d = ImageDraw.Draw(img)
    c = (15, 23, 42)
    d.rounded_rectangle(s(262, 184, 762, 604), radius=60 * K, outline=c, width=22 * K)
    d.line(s(262, 300, 762, 300), fill=c, width=22 * K)
    for x in (380, 512, 644):
        d.ellipse(s(x - 34, 384, x + 34, 452), fill=c)
    d.line(s(362, 130, 362, 230), fill=c, width=22 * K)
    d.line(s(662, 130, 662, 230), fill=c, width=22 * K)
    for x in (362, 662):
        d.ellipse(s(x - 11, 119, x + 11, 141), fill=c)
        d.ellipse(s(x - 11, 219, x + 11, 241), fill=c)
    return finish(img)


def landscape():
    """Photo-like: smooth sky, radial sun glow, textured hills, blur and sensor noise (no outlines)."""
    rng = np.random.default_rng(11)
    w, h = W * K, H * K
    img = lin_gradient((w, h), (96, 165, 250), (253, 230, 200), 90)
    glow = radial_gradient((w, h), (255, 244, 214), (253, 230, 200), 720 * K, 250 * K, 260 * K)
    m = Image.new('L', (w, h), 0)
    ImageDraw.Draw(m).ellipse(s(460, 0, 980, 500), fill=255)
    img.paste(glow, (0, 0), m.filter(ImageFilter.GaussianBlur(60 * K)))
    for base, col, amp, seed in ((470, (74, 124, 89), 70, 1), (560, (52, 96, 64), 50, 2), (660, (35, 70, 45), 30, 3)):
        xs = np.arange(0, W + 1, 8)
        r = np.random.default_rng(seed)
        ys = base + np.convolve(r.normal(0, amp, len(xs) + 20), np.ones(21) / 21, 'valid')[:len(xs)]
        poly = [(x * K, y * K) for x, y in zip(xs, ys)] + [(W * K, H * K), (0, H * K)]
        tex = np.asarray(Image.new('RGB', (w, h), col)).astype(np.float32)
        tex *= (1 + 0.08 * ndimage_zoom(rng.normal(0, 1, (H // 8, W // 8)), (h, w)))[..., None]
        mm = Image.new('L', (w, h), 0)
        ImageDraw.Draw(mm).polygon(poly, fill=255)
        img.paste(Image.fromarray(np.clip(tex, 0, 255).astype(np.uint8)), (0, 0), mm)
    return finish(img, soft=1.0, noise=3.0, seed=5)


def ndimage_zoom(a, shape):
    return np.asarray(Image.fromarray(a.astype(np.float32)).resize((shape[1], shape[0]), Image.BICUBIC))


SCENES = {'face': face, 'logo-flat': logo_flat, 'icon-outline': icon_outline, 'sphere': sphere, 'rings': rings,
          'stripes': stripes, 'thin-lines': thin_lines, 'gradient-bg': gradient_bg, 'leaves': leaves,
          'badge': badge, 'line-icon': line_icon, 'landscape': landscape}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, fn in SCENES.items():
        fn().save(OUT / f'{name}.png')
    print(f'wrote {len(SCENES)} images to {OUT}')


if __name__ == '__main__':
    main()
