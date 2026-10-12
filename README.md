# PNG to SVG Vectorize

<p align="center"><img src="assets/icons/icon-256.png" width="128" alt="PNG to SVG Vectorize logo"></p>

[![CI](https://github.com/RidhuanDEV/png-to-svg-vectorize/actions/workflows/ci.yml/badge.svg)](https://github.com/RidhuanDEV/png-to-svg-vectorize/actions/workflows/ci.yml)

Turn **raster cartoon illustrations** (PNG/WebP/JPEG — e.g. from image generators or scans) into **editable, library-free SVG**:

- **Gradient fills** — soft shading becomes one region with a fitted `linearGradient`, not posterized bands or blotches.
- **Crisp outlines** — ink lines are separated by color unmixing into a sub-pixel accurate, smooth outline layer.
- **Pure SVG** — only `<path>`, `<rect>`, `<g>`, `<linearGradient>`. No `<image>`, CSS or scripts. Works in browsers,
  Figma/Illustrator/Inkscape, Flutter (`flutter_svg`), Android/iOS vector pipelines.
- **Safe to inline** — gradient ids are prefixed per file, so many SVGs can share one page.
- **Compact** — relative path commands with minimal number syntax (~50% smaller than absolute coordinates).

```text
input.png ──► outline separation ──► fill layer (regions + gradients) ──► SVG
               (ink alpha map)        (segmentation, union-find merge)    <defs> gradients
                                                                          <g id="fill">
                                                                          <g id="outline">
```

> **Status:** v0.1 — command line + Python library. A desktop app for **Windows and macOS** is planned for v1.0
> (see [docs/PLAN.md](docs/PLAN.md)).

## Install

```bash
git clone https://github.com/RidhuanDEV/png-to-svg-vectorize.git
cd png-to-svg-vectorize
pip install -e .            # add [dev] for tests
```

Requirements: Python ≥ 3.10, numpy, scipy, Pillow, [vtracer](https://github.com/visioncortex/vtracer) (MIT).

## Usage

```bash
png2svg hero.png                         # -> hero.svg
png2svg scenes/*.png -o out/ --report    # batch + similarity check (needs Chrome or Edge)
png2svg logo.png --flat --no-outline     # flat colors, no outline layer
```

```python
from PIL import Image
from pngsvg import Options, vectorize

result = vectorize(Image.open('hero.png'), Options(id_prefix='hero'))
open('hero.svg', 'w', encoding='utf-8').write(result.svg)
print(result.regions, result.gradients, result.outline_paths)
```

### Options

| Option | Default | Meaning |
|---|---|---|
| `scale` | auto (long side ≈ 4500 px) | tracing upscale; higher = smoother curves, bigger files |
| `outlines` | `True` | separate ink outlines into their own layer |
| `gradients` | `True` | gradient fills (`False` = flat colors) |
| `regions.merge_de` | `9` | neighbours closer than this ΔE may merge (soft shading). Lower keeps more detail |
| `regions.fit_de` | `3.5` | ...only if one linear gradient still explains the union (extra error per px, ΔE) |
| `regions.gradient_min_area` | `300` | smaller regions are always solid fills |
| `outline.core_de` | `9` | ΔE to the ink color for pure outline pixels |
| `outline.thin_depth` | `25` | thin anti-aliased lines: how much darker (L\*) than surroundings |
| `outline.halo_*` | — | flattening of light rims left by over-sharpened generators |

## How it works

1. **Ink detection.** The ink color is the median of the darkest pixels. Pure ink = close to it (ΔE), very dark,
   or a *thin* dark line (black top-hat) of ink-like hue — so 1–2 px lines that never reach full ink still count,
   while large dark areas (hair) and brown/grey strokes stay colors.
2. **Unmixing.** Around ink, each pixel is modelled as `alpha·ink + (1−alpha)·behind`. Pixels on that segment are
   anti-aliasing (alpha = position); pixels off it are real colors (lips, blush). The continuous alpha map is
   upsampled and thresholded → smooth outline with sub-pixel accuracy. Light same-hue rims next to ink
   (sharpening halos) are flattened.
3. **Regions.** The image without ink is edge-preserving smoothed (guided filter), palette-reduced and split into
   connected regions, then merged with a union-find: similar neighbours **only if one linear gradient still
   explains their union** (evaluated in O(1) from per-region sufficient statistics), tiny regions, and thin rims
   hugging outlines. So skin shading merges, while rings, blush and patterns stay separate.
4. **Gradients.** Per region, a linear regression of color vs. position gives the gradient direction; three
   stops are measured from the source pixels. Weak gradients become solid fills.
5. **Tracing.** Each region mask is upsampled, smoothed, slightly dilated (no seams) and traced with vtracer;
   painted largest first, outlines on top.

## Quality check

`--report` renders the SVG with headless Chrome/Edge and prints similarity (100 − mean abs error %, and % of
pixels within 24/255). Typical cartoon illustrations reach 98–99 %. Always also compare visually at 2× zoom —
a single number can hide local defects.

## Limitations

- Designed for **cartoon / flat illustration** styles with ink outlines. Photos and painterly art produce many
  regions and large files.
- Only linear gradients (no radial or mesh). Round soft blobs (blush) become flat or linear-shaded regions.
- File size grows with detail (300 KB – 1 MB for a 1536×1024 detailed scene).

## Tests

```bash
pip install -e .[dev]
pytest -q
```

## Roadmap

See [docs/PLAN.md](docs/PLAN.md): better curve fitting (fewer nodes, smaller files), shared region boundaries,
radial gradients, parallel processing, and a desktop app for Windows and macOS.

## License

[MIT](LICENSE) © Ridhuan Rangga Kusuma. Uses [vtracer](https://github.com/visioncortex/vtracer) (MIT).

---

## Ringkasan (Bahasa Indonesia)

Alat untuk mengubah **ilustrasi kartun raster** (PNG/WebP/JPEG) menjadi **SVG path murni** yang bisa diedit:
isian bergradasi (kulit mulus, tanpa bercak), garis luar tajam dan akurat sampai sub-piksel, tanpa library/CSS/raster,
ID gradien unik per file, dan ukuran ringkas. Pemakaian: `png2svg gambar.png` (hasil `gambar.svg`),
atau `png2svg folder/*.png -o hasil/ --report` untuk banyak berkas sekaligus beserta ukuran kemiripan.
Selalu periksa juga secara visual pada perbesaran 2×.
