# Benchmark

Run with `python bench/synthetic.py` once, then `python bench/run.py` (needs Chrome or Edge for the similarity
render). Compare against the committed baseline with `python bench/run.py --baseline bench/baseline.json`
(exit code 1 on regression: similarity −0.3 points or size +10 %). `bench/baseline.json` always holds the latest
accepted synthetic numbers (currently v0.3 / M3). `--jobs 4` times with a warm process pool, like
the CLI and the app.

- **Synthetic set** (`bench/synthetic.py`, 12 procedural images, license-free): face with soft blush, flat logo,
  outlined icon, radial-gradient sphere, faint concentric rings, stripes + dots, thin lines, gradient background,
  overlapping leaves, star badge, line icon (v0.3+), photo-like landscape (v0.3+).
- **Comparison set (E7, v1.0+)**: 27 CC0 / public-domain images from Wikimedia Commons — 13 cartoons (10 rendered
  clipart, 3 raster illustrations), 3 flat illustrations, 4 flags (logo-like geometry), 4 icons, 2 paintings and a
  photo. Not stored in git: `python bench/fetch_sets.py` downloads them and checks SHA-256; sources and licenses in
  [bench/sets/SOURCES.md](../bench/sets/SOURCES.md). CI checks it against `bench/baseline-sets.json`.
- **Private set**: 15 cartoon illustrations from the Turion app (image-generator art, 1536×1024 / 1774×887). Not
  published; numbers reported for reference.

Machine: Windows 11 laptop, Python 3.13, single process.

## v1.6 — logo engine (2026-10-25)

The `logo` (and new `pixel`) preset uses the flat engine; all other presets are unchanged (the E7 and synthetic
baselines use `cartoon`). On the Turion logo fixture: 4 paths, 468 B, IoU 0.9984 / 0.9973, mean ΔE 0.06 away from
edges, ~1.4 s — see [logo-engine.md](logo-engine.md) for the before/after table. In the gallery, `flag-brazil` and
`icon-shop` (logo style) were regenerated.

## v1.5 — center lines, layers, editing (2026-10-25)

Default output is byte-identical to v1.4 (same check). New modes are opt-in and verified by tests rather than the
similarity bench, because they deliberately change what is drawn:
- **Center lines** (`layout=centerline`): a synthetic drawing (straight line, circle, sine wave, V, rectangle) gives
  10 stroked paths in 0.13 s; the circle is one closed loop. Stroke widths are estimated from the ink (75th percentile
  of the distance to the paper along the line, ±1 px on slanted lines). PDF of the result rendered by the Windows PDF
  engine matches the SVG render at 99.85 %.
- **Layers per color** (`layers=true`, implies cut-out): flag-brazil 99.86 % similarity, one `<g id="color-…">` per
  color.

## v1.4 — studio options (2026-10-25)

Default output is **byte-identical** to v1.3 (checked on three E7 images × three presets), so every baseline above
still holds. The new modes, on 12 E7 images (cartoons, flags, icons; transparent pixels compared on white), cartoon
preset, rendered and compared with the original:

| Mode | Similarity (median) | Size (median) | Time (median) |
|---|---|---|---|
| default | 99.82 % | 39 KB | 7.2 s |
| cutout (`layout=cutout`) | 99.82 % | 44 KB | 7.4 s |
| 16 flat colors (`max_colors=16`) | 99.80 % | 38 KB | 6.8 s |
| 8 flat colors | 99.75 % | 36 KB | 6.6 s |
| 4 flat colors | 98.89 % | 32 KB | 7.0 s |

- A limited palette costs little quality down to ~8 colors: palette colors come from an area-weighted k-means of the
  region colors, and touching regions with the same color merge (fewer shapes).
- Cut-out shapes keep every hole (`fill-rule="evenodd"`), +13 % size, same look.
- Exports, size relative to the SVG (median): **PDF 0.6×** (compressed stream), EPS 2.0×, DXF 4.2× (curves flattened to
  polylines, 0.25 px). PDF pages rendered with the Windows PDF engine match the SVG render at 99.9 % (gradients
  included).

## v1.3 — optional AI step (2026-10-25)

`python bench/ai_restore.py MODELS_DIR --limit 10` — a **restoration** test: each clean E7 image is first degraded like
a typical web picture (half size + JPEG quality 60), then vectorized without AI and with each AI model (x4 upscale,
resized to 2× the photo, `decimals` one lower). The SVGs are rendered at the ORIGINAL size and compared with the
CLEAN original, so a gain means detail was recovered, not that the damage was copied. Default preset, CPU
(DirectML gives the same pixels), single process.

| image | no AI | AI general | AI illustration |
|---|---|---|---|
| astronaut.png | 98.69% · 51 KB | 98.90% · 95 KB | 98.98% · 88 KB |
| basketball-mascot.png | 99.42% · 52 KB | 99.75% · 54 KB | 99.72% · 46 KB |
| caticorn.png | 98.82% · 80 KB | 99.13% · 131 KB | 99.20% · 94 KB |
| cow.png | 99.28% · 20 KB | 99.34% · 39 KB | 99.33% · 33 KB |
| cute-girl.png | 97.86% · 93 KB | 98.63% · 221 KB | 98.60% · 188 KB |
| donkey.png | 99.43% · 11 KB | 99.52% · 19 KB | 99.52% · 20 KB |
| earth-apollo17.jpg | 93.09% · 301 KB | 94.58% · 921 KB | 94.33% · 906 KB |
| fish-mascot.png | 99.59% · 24 KB | 99.73% · 39 KB | 99.75% · 34 KB |
| flag-brazil.png | 98.86% · 59 KB | 98.86% · 84 KB | 99.39% · 63 KB |
| flag-kiribati.png | 98.23% · 65 KB | 98.57% · 158 KB | 98.71% · 46 KB |

- **no AI**: median similarity 98.86%, median size 59 KB, median vectorize 2.5 s
- **AI general**: median similarity 99.13%, median size 95 KB, median vectorize 8.2 s, AI 1.1 s
- **AI illustration**: median similarity 99.33%, median size 63 KB, median vectorize 7.6 s, AI 2.9 s

- Target of PLAN-v2 M9 (+0.3 points on small/damaged pictures) is met by the **illustration** model: **+0.47** median,
  +7 % median size; it wins on 8 of 10 images. The *general* model gains less (+0.27) and makes files 60 % larger.
- Cost: vectorizing the 2× picture takes ~3× longer, plus the model itself (2.9 s on a laptop CPU at these sizes).
- Decision: AI stays **optional** (model downloaded on request). Default mode *Automatic* applies it only where it
  helps — photos under 1000 px on the long side, or JPEGs; large clean PNGs skip it, so the E7/synthetic baselines
  (no AI) are unchanged. The illustration model is the default.
- Not measured: "Always" on large clean PNGs (expected: little gain for a large time cost), and the region-count
  target (−20 % segments).

## v1.0 — comparison set E7 (2026-10-12)

Default preset (`cartoon`) on every image, 4 worker processes:

| Category | Images | Similarity (median) | Size (median) |
|---|---|---|---|
| Cartoon (rendered clipart) | 10 | 99.58 % | 76 KB |
| Cartoon (raster illustration) | 3 | 99.57 % | 20 KB |
| Flat illustration | 3 | 99.72 % | 72 KB |
| Logo-like (flags) | 4 | 99.81 % | 20 KB |
| Icon | 4 | 99.94 % | 5 KB |
| Painting / photo | 3 | 94.26 % | 1.1 MB |
| **All** | 27 | **99.72 %** | 57 KB |

Paintings and photos are not the target of the default preset: with `--preset poster` the three files shrink by
50–57 % (Earth 1.2 MB → 0.56 MB, Great Wave 0.64 → 0.30 MB, Starry Night 1.95 → 0.84 MB) at a similar similarity
(95.18 / 92.73 / 92.17 %).

Found and fixed while building the set: transparent PNGs were flattened onto black (now white); when the darkest
pixels are a colored dark AREA (a purple flag, deep blue water) instead of lines, the ink color is taken from line
pixels (astronaut: purple outlines → black, +0.44, −27 % size). The synthetic and Turion sets are unchanged by both.

### Visual checklist (PLAN §8) at 2× zoom

| Check | Result |
|---|---|
| Lines not jagged | ✅ cartoon outlines and flag/icon edges are smooth; straight edges straight (sub-pixel edges, v0.3) |
| No gaps between regions | ✅ none found (shared boundaries, v0.2) |
| Gradients without bands | ⚠️ mostly ✅; glossy, strongly non-linear shading (penguin beak, metallic highlights) still shows a few soft bands |
| Mouths / eyes intact | ✅ on all cartoon faces checked (cute-girl, shipment, silver-hair-girl, Turion set) |
| Blush kept | ✅ for clear blush; ⚠️ very faint tiny spots (freckle dots) merge into skin |
| No light rims | ✅ |
| Hairlines | ⚠️ lines thinner than ~1.5 px that are mostly anti-aliasing (the sun rays on the Kiribati flag) are lost |

### Comparison set results

| Image | Similarity | Within 24 | Size (bytes) | Segments | Regions | Time (s) |
|---|---|---|---|---|---|---|
| astronaut | 99.44% | 98.4% | 102670 | 4567 | 53 | 7.1 |
| basketball-mascot | 99.83% | 99.5% | 70176 | 2957 | 73 | 6.6 |
| caticorn | 99.81% | 99.4% | 94987 | 3469 | 69 | 6.6 |
| cow | 99.82% | 99.4% | 35199 | 1363 | 30 | 6.1 |
| cute-girl | 99.52% | 98.1% | 178956 | 7115 | 209 | 10.7 |
| donkey | 99.83% | 99.3% | 45186 | 1856 | 17 | 6.3 |
| earth-apollo17 | 94.44% | 80.4% | 1198954 | 54803 | 1147 | 16.9 |
| fish-mascot | 99.62% | 98.0% | 58415 | 2425 | 58 | 10.6 |
| flag-brazil | 99.86% | 99.5% | 32805 | 1254 | 59 | 4.0 |
| flag-kiribati | 99.26% | 97.8% | 56412 | 2499 | 29 | 3.0 |
| flag-nepal | 99.92% | 99.5% | 8959 | 334 | 8 | 6.0 |
| flag-south-africa | 99.76% | 99.3% | 6525 | 237 | 9 | 3.5 |
| flying-plane | 99.72% | 99.0% | 63018 | 2444 | 83 | 5.2 |
| futuristic-mascot | 99.11% | 93.5% | 20011 | 591 | 27 | 4.1 |
| great-wave | 94.26% | 78.0% | 639638 | 28930 | 398 | 9.8 |
| icon-cat | 99.97% | 99.9% | 2552 | 94 | 1 | 2.5 |
| icon-exclamation | 99.92% | 99.6% | 3421 | 120 | 7 | 1.6 |
| icon-flask | 99.96% | 99.8% | 7025 | 269 | 11 | 1.6 |
| icon-shop | 99.81% | 98.7% | 34147 | 1335 | 79 | 1.9 |
| kazoo | 99.88% | 99.5% | 11913 | 442 | 19 | 5.0 |
| mountain-landscape | 99.75% | 99.6% | 74089 | 2852 | 61 | 6.1 |
| penguin | 99.08% | 99.0% | 84868 | 2925 | 100 | 8.4 |
| popcorn | 99.57% | 99.1% | 33523 | 1298 | 35 | 5.0 |
| robot | 99.53% | 98.4% | 70776 | 2876 | 64 | 6.6 |
| shipment | 99.67% | 99.2% | 93902 | 3751 | 97 | 6.5 |
| silver-hair-girl | 99.14% | 98.7% | 132938 | 5439 | 76 | 7.4 |
| starry-night | 92.07% | 55.0% | 1954044 | 90841 | 2035 | 22.3 |
| **median** | 99.72% | 99.1% | 58415 | 2444 | 59 | 6.1 |

## v0.3 — M3: radial gradients, speed, presets (2026-10-12)

Changes: least-squares gradient stops at offsets 0/.5/1 (a straight ramp is reproduced almost exactly), elliptical
`radialGradient` with a cone fit, radial growth that joins concentric bands of a ball/glow into one region,
sub-pixel fill boundaries from anti-aliasing + boundary refinement (straight edges, sharp tips), wider
anti-aliasing band merging, adaptive ink detection (thin outlines covering < 2 % of the image), statistics
aggregated per initial label (segmentation ~2x faster), optional process pool (`executor=`, CLI `--jobs`),
presets `cartoon` / `flat` / `logo` / `poster`.

| Set | Similarity (median) | Size (median) | Segments (median) | Time (median) |
|---|---|---|---|---|
| Synthetic (9 shared images, vs v0.2) | 99.45 → 99.46 % | 8.5 → 8.7 KB | 329 → 349 | 2.9 → 3.4 s (serial) |
| Private (Turion, vs v0.2) | 98.65 → 98.65 % | 188 → 165 KB (−10 %) | 6 547 → 6 233 | 10.1 s serial → **7.2 s** with `--jobs 4` |

- M3 target "≤ 8 s per 1536×1024 image": met for the median (7.2 s with 4 worker processes); the heaviest scenes
  take 8.0–9.8 s. Serial runs are ~8–9 s. Timing on this laptop varies ±20 % between runs.
- Notable: `sphere` 17 → 8 regions, one radial gradient instead of concentric bands (−48 % size, +0.15);
  `thin-lines` +1.34 (14 thin lines were lost before; the size grows because they are now drawn); `sukses` blush
  is now soft-edged; `logo-flat` gets exactly its 6 shapes with the `logo` preset.
- Known trade-off: very faint, tiny color spots (e.g. a light pink dot on a chin) can merge into the surrounding
  skin.

Presets on the logo/icon images (similarity / size / regions):

| Image | cartoon | logo |
|---|---|---|
| logo-flat | 99.90 % / 4 KB / 8 | 99.92 % / 4 KB / 6 |
| badge | 99.90 % / 6 KB / 11 | 99.90 % / 3 KB / 6 |
| icon-outline | 99.84 % / 5 KB / 6 | 99.84 % / 5 KB / 6 |
| line-icon | 99.90 % / 3 KB / 1 | 99.90 % / 3 KB / 1 |

`poster` on the photo-like `landscape`: 98.52 % / 21 KB / 13 regions vs `cartoon` 98.48 % / 67 KB / 40.

### Synthetic set (v0.3, delta vs v0.2)

| Image | Similarity | Within 24 | Size (bytes) | Segments | Regions | Time (s) |
|---|---|---|---|---|---|---|
| badge | 99.90% | 99.6% | 7101 | 252 | 11 | 2.8 |
| face | 98.73% (+0.01) | 99.4% | 7259 (+8%) | 189 (-11%) | 11 | 3.5 (+1%) |
| gradient-bg | 99.60% (+0.15) | 99.6% | 8929 (+3%) | 349 (+6%) | 4 | 3.3 (-13%) |
| icon-outline | 99.84% (-0.01) | 99.8% | 5884 (+3%) | 237 (+3%) | 6 | 3.0 (+0%) |
| landscape | 98.45% | 99.8% | 59093 | 2496 | 35 | 4.9 |
| leaves | 99.18% (+0.16) | 99.3% | 33835 (-24%) | 1262 (-18%) | 22 | 4.2 (+46%) |
| line-icon | 99.90% | 99.9% | 3258 | 133 | 1 | 2.7 |
| logo-flat | 99.90% (+0.01) | 99.7% | 4316 (-17%) | 158 (-16%) | 8 | 2.9 (+6%) |
| rings | 99.33% (-0.05) | 99.4% | 26006 (-26%) | 1089 (-26%) | 12 | 4.0 (+33%) |
| sphere | 99.83% (+0.15) | 99.8% | 7331 (-48%) | 251 (-54%) | 8 | 3.0 (+75%) |
| stripes | 99.46% (-0.01) | 98.5% | 23725 (+5%) | 847 (+5%) | 101 | 3.4 (+15%) |
| thin-lines | 98.99% (+1.34) | 98.2% | 24299 (+200%) | 1096 (+307%) | 2 | 3.7 (+80%) |
| **median** | 99.53% | 99.6% | 8130 | 300 | 10 | 3.3 |

### Private set (v0.3, `--jobs 4`, delta vs v0.2)

| Image | Similarity | Within 24 | Size (bytes) | Segments | Regions | Time (s) |
|---|---|---|---|---|---|---|
| acuan-gagal | 99.19% (+0.03) | 98.9% | 115286 (-15%) | 4475 (-14%) | 102 | 6.9 (-32%) |
| acuan-sukses | 99.11% (+0.09) | 99.0% | 82976 (-15%) | 2984 (-16%) | 86 | 8.0 (-12%) |
| promo-gizi | 98.56% (-0.01) | 96.0% | 207949 (-9%) | 7653 (-1%) | 377 | 7.9 (-23%) |
| promo-kendaraan | 98.40% (+0.00) | 95.9% | 194116 (-10%) | 7302 (-3%) | 226 | 8.4 (-16%) |
| promo-kesehatan | 98.61% (+0.11) | 95.8% | 321756 (-15%) | 11175 (-11%) | 651 | 9.8 (-29%) |
| promo-keuangan | 98.62% (-0.02) | 96.0% | 176930 (-14%) | 6574 (-9%) | 228 | 6.8 (-36%) |
| promo-offline | 98.64% (-0.01) | 96.5% | 196326 (-10%) | 7197 (-7%) | 210 | 7.1 (-31%) |
| promo-olahraga | 98.57% (-0.01) | 96.2% | 162651 (-8%) | 6109 (-0%) | 173 | 7.2 (-26%) |
| promo-peluncuran | 98.75% (-0.03) | 96.3% | 169054 (-12%) | 6233 (-5%) | 224 | 7.4 (-45%) |
| promo-pendidikan | 98.51% (+0.03) | 95.5% | 192077 (-13%) | 7085 (-7%) | 223 | 7.0 (-30%) |
| promo-pengingat | 98.65% (+0.03) | 96.5% | 127433 (-8%) | 4790 (-5%) | 123 | 6.4 (-29%) |
| promo-pola-hidup | 98.79% (-0.01) | 97.1% | 142849 (-13%) | 5498 (-6%) | 182 | 7.0 (-19%) |
| promo-premium | 98.82% (+0.01) | 97.7% | 209685 (-9%) | 8042 (-3%) | 255 | 7.9 (-29%) |
| promo-rumah | 98.91% (-0.02) | 97.1% | 152043 (-6%) | 5624 (-1%) | 181 | 7.2 (-23%) |
| promo-sambutan | 98.91% (-0.01) | 97.5% | 114746 (-13%) | 4476 (-6%) | 126 | 6.8 (-26%) |
| **median** | 98.65% | 96.5% | 169054 | 6233 | 210 | 7.2 |

## v0.2 — M2: shared boundaries + Bezier fitting (2026-10-12)

Changes: planar map (every boundary between two regions is traced once and shared, no overlap), own cubic
Bezier fitting (Schneider) with corner detection, looser tolerance for fill boundaries hidden under the outline
layer, anti-aliasing sliver/speckle merging, size-aware gradient merging, vtracer dropped. Deltas are against v0.1.

| Set | Similarity (median) | Size (median) | Segments (median) | Time (median) |
|---|---|---|---|---|
| Synthetic | 99.47 → 99.45 % | 96 KB → 8.5 KB (−91 %) | 4 882 → 329 (−93 %) | 7.8 → 2.9 s |
| Private (Turion) | 98.57 → 98.65 % | 449 KB → 188 KB (−58 %) | 20 973 → 6 547 (−69 %) | 18.3 → 10.1 s |

M2 targets (segments −50 %, size −40 %, similarity drop ≤ 0.3) are met on both sets. Visual check at 3× zoom:
smoother curves than v0.1 (no stair-steps), no seams, blush/mouth details kept, fewer stray specks.

### Synthetic set (v0.2, delta vs v0.1)

| Image | Similarity | Within 24 | Size (bytes) | Segments | Regions | Time (s) |
|---|---|---|---|---|---|---|
| face | 98.72% (+0.16) | 99.4% | 6705 (-93%) | 213 (-96%) | 12 | 3.5 (-62%) |
| gradient-bg | 99.45% (-0.01) | 99.6% | 8675 (-86%) | 329 (-90%) | 4 | 3.8 (-58%) |
| icon-outline | 99.85% (+0.03) | 99.8% | 5703 (-87%) | 229 (-89%) | 6 | 2.9 (-61%) |
| leaves | 99.02% (+0.05) | 98.1% | 44677 (-71%) | 1542 (-80%) | 110 | 2.9 (-61%) |
| logo-flat | 99.88% (+0.03) | 99.6% | 5186 (-89%) | 189 (-92%) | 11 | 2.7 (-66%) |
| rings | 99.37% (+0.00) | 99.7% | 35181 (-87%) | 1463 (-90%) | 22 | 3.0 (-70%) |
| sphere | 99.68% (+0.06) | 99.7% | 14195 (-90%) | 546 (-93%) | 19 | 1.7 (-71%) |
| stripes | 99.47% (-0.02) | 98.9% | 22565 (-83%) | 804 (-88%) | 101 | 3.0 (-62%) |
| thin-lines | 97.64% (-0.02) | 97.5% | 8109 (-79%) | 269 (-86%) | 46 | 2.0 (-63%) |
| **median** | 99.45% | 99.6% | 8675 | 329 | 19 | 2.9 |

### Private set (v0.2, delta vs v0.1)

| Image | Similarity | Within 24 | Size (bytes) | Segments | Regions | Time (s) |
|---|---|---|---|---|---|---|
| acuan-gagal | 99.17% (+0.07) | 98.8% | 136312 (-66%) | 5179 (-72%) | 132 | 10.2 (-44%) |
| acuan-sukses | 99.02% (+0.07) | 98.9% | 98151 (-74%) | 3548 (-80%) | 132 | 9.1 (-50%) |
| promo-gizi | 98.56% (+0.02) | 96.0% | 229269 (-54%) | 7764 (-65%) | 475 | 10.2 (-48%) |
| promo-kendaraan | 98.39% (+0.05) | 95.9% | 214862 (-53%) | 7521 (-64%) | 288 | 10.1 (-47%) |
| promo-kesehatan | 98.50% (+0.10) | 96.0% | 376546 (-49%) | 12575 (-63%) | 897 | 13.8 (-50%) |
| promo-keuangan | 98.64% (+0.07) | 96.0% | 206698 (-57%) | 7256 (-67%) | 289 | 10.6 (-47%) |
| promo-offline | 98.65% (+0.14) | 96.5% | 218471 (-55%) | 7773 (-65%) | 272 | 10.2 (-46%) |
| promo-olahraga | 98.58% (+0.04) | 96.2% | 176572 (-58%) | 6129 (-68%) | 209 | 9.8 (-40%) |
| promo-peluncuran | 98.77% (+0.06) | 96.4% | 192396 (-58%) | 6547 (-69%) | 296 | 13.4 (-25%) |
| promo-pendidikan | 98.48% (+0.09) | 95.5% | 220060 (-58%) | 7590 (-69%) | 333 | 10.0 (-46%) |
| promo-pengingat | 98.62% (+0.05) | 96.5% | 138622 (-65%) | 5038 (-73%) | 166 | 8.9 (-44%) |
| promo-pola-hidup | 98.80% (+0.13) | 97.2% | 164820 (-57%) | 5867 (-67%) | 266 | 8.7 (-45%) |
| promo-premium | 98.81% (+0.09) | 97.7% | 230554 (-62%) | 8292 (-71%) | 325 | 11.1 (-50%) |
| promo-rumah | 98.93% (+0.06) | 97.2% | 161341 (-57%) | 5673 (-67%) | 212 | 9.3 (-45%) |
| promo-sambutan | 98.92% (-0.03) | 97.5% | 131454 (-63%) | 4776 (-71%) | 164 | 9.2 (-38%) |
| **median** | 98.65% | 96.5% | 192396 | 6547 | 272 | 10.1 |

## v0.1 baseline (2026-10-12)

### Synthetic set

| Image | Similarity | Within 24 | Size (bytes) | Segments | Regions | Time (s) |
|---|---|---|---|---|---|---|
| face | 98.56% | 99.1% | 96120 | 4882 | 69 | 9.2 |
| gradient-bg | 99.47% | 99.7% | 62038 | 3173 | 14 | 9.1 |
| icon-outline | 99.81% | 99.6% | 42758 | 2179 | 8 | 7.6 |
| leaves | 98.97% | 97.8% | 156408 | 7822 | 348 | 7.4 |
| logo-flat | 99.85% | 99.5% | 48180 | 2488 | 288 | 7.9 |
| rings | 99.37% | 99.7% | 274245 | 14306 | 128 | 10.0 |
| sphere | 99.62% | 99.5% | 141684 | 7487 | 24 | 6.0 |
| stripes | 99.49% | 98.4% | 130265 | 6916 | 142 | 7.8 |
| thin-lines | 97.67% | 97.5% | 37771 | 1896 | 142 | 5.6 |
| **median** | 99.47% | 99.5% | 96120 | 4882 | 128 | 7.8 |

### Private set (Turion illustrations)

| Image | Similarity | Within 24 | Size (bytes) | Segments | Regions | Time (s) |
|---|---|---|---|---|---|---|
| acuan-gagal | 99.10% | 98.3% | 395959 | 18655 | 604 | 18.3 |
| acuan-sukses | 98.94% | 98.4% | 370628 | 17437 | 569 | 18.2 |
| promo-gizi | 98.55% | 95.7% | 494092 | 22501 | 668 | 19.7 |
| promo-kendaraan | 98.34% | 95.7% | 459659 | 20977 | 396 | 19.2 |
| promo-kesehatan | 98.40% | 95.5% | 743061 | 33717 | 970 | 27.6 |
| promo-keuangan | 98.57% | 95.7% | 477963 | 22011 | 673 | 19.9 |
| promo-offline | 98.51% | 96.1% | 483387 | 22445 | 403 | 19.0 |
| promo-olahraga | 98.53% | 96.0% | 415956 | 19032 | 249 | 16.3 |
| promo-peluncuran | 98.71% | 96.2% | 460184 | 20973 | 836 | 18.0 |
| promo-pendidikan | 98.38% | 95.2% | 526618 | 24275 | 543 | 18.6 |
| promo-pengingat | 98.57% | 96.3% | 395252 | 18584 | 443 | 16.0 |
| promo-pola-hidup | 98.67% | 96.8% | 381325 | 17767 | 388 | 16.0 |
| promo-premium | 98.72% | 96.9% | 605496 | 28554 | 627 | 22.2 |
| promo-rumah | 98.87% | 97.0% | 374213 | 17156 | 412 | 16.9 |
| promo-sambutan | 98.94% | 97.3% | 353154 | 16394 | 280 | 14.8 |
| **median** | 98.57% | 96.2% | 459659 | 20973 | 543 | 18.3 |
