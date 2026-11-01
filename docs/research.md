# How PNG to SVG Vectorize works, how well, and why

*A technical report: problem, method, design choices with their justification, measured results, known errors.
It is written like a short thesis, but it is not one: the claims are checked by code and numbers in this
repository, not by peer review. Everything here can be reproduced with the commands in §6.*

> **Ringkasan (Bahasa Indonesia).** Laporan ini menjelaskan masalah vektorisasi gambar raster, metode yang
> dipakai aplikasi ini di tiap tahap beserta alasannya dan kaitannya dengan penelitian terdahulu, cara mengukur
> kualitas (apa arti "99,9 %", dan mengapa skor 99 % bisa menyembunyikan cacat yang terlihat), hasil benchmark pada
> 45 gambar berlisensi bebas beserta penilaian model vision yang dikalibrasi, perbandingan dengan VTracer dan Potrace
> pada gambar yang sama, uji statistik berpasangan (Wilcoxon, interval kepercayaan bootstrap), uji ketahanan terhadap
> JPEG, pengecilan, dan derau, kesalahan algoritma yang ditemukan dan
> diperbaiki, serta peningkatan yang diambil dari literatur (§8): yang terbukti meningkatkan hasil dipakai, yang
> tidak dicatat sebagai hasil negatif. Langkah AI (Real-ESRGAN) bersifat opsional; manfaatnya diukur di §5.2 dan
> hanya dipakai otomatis bila terbukti membantu. Kontribusi orisinal proyek ini dirangkum di §8.4.

## 1. The problem

A raster image is a grid of colored pixels; an SVG is a list of shapes (paths with fills). *Vectorization* turns
the first into the second. A good result must satisfy five criteria that pull against each other, as the survey by
Dziuba et al. [1] lists them: **similarity** to the picture, **simplicity** (few paths and points: small, editable
files), **speed**, **versatility** (works on many kinds of pictures) and **control** for the user. Their conclusion is
also ours: no automatic method is fast, faithful *and* simple on every kind of picture. Optimisation-based methods
(DiffVG [2], LIVE [3]) reach high fidelity but need minutes per image and a GPU; learned methods (StarVector [4],
SuperSVG [5]) generate SVG code directly but work well only within the domain they were trained on (icons, emoji)
and need large models.

This project targets the pictures people most often want as SVG — **cartoons, flat illustrations, logos, icons,
flags** — on an ordinary laptop, offline, in seconds, with files a designer can open and edit. It does not try to
turn photographs into vectors (§7.3 explains why that is a different problem).

## 2. Two engines

| | Region engine (`cartoon`, `flat`, `poster`) | Flat engine (`logo`, `pixel`) |
|---|---|---|
| For | illustrations with shading and ink outlines | flat-color logos, icons, flags, pixel art |
| Fills | flat colors, linear and elliptical radial gradients | flat colors from a small palette |
| Outlines | separate ink layer with sub-pixel edges | none: every shape is one path |
| Geometry | smooth cubic Béziers | straight lines, arcs and Béziers; sharp corners |
| Background | a `<rect>` (or removed on request) | left out, SVG trimmed to the artwork |
| Code | `core.py`, `regions.py`, `outline.py`, `planar.py`, `curves.py`, `gradients.py` | `logo.py` ([docs](logo-engine.md)) |

Both are deterministic (same input and options give a byte-identical SVG), run on the CPU, and use only NumPy,
SciPy and Pillow.

## 3. Method, stage by stage, and why

### 3.1 Region engine

1. **Ink outlines are separated first** (`outline.py`). Every pixel near a dark line is modelled as a blend
   `p = α·I + (1 − α)·B` of the ink color *I* and the color behind it *B*. Where the pixel lies on the segment I→B,
   α is its position (anti-aliasing). Otherwise it is a real color (lips, blush) and α = 0. The continuous α map is
   upsampled and thresholded into a crisp, sub-pixel outline layer, and the fill layer sees *B* instead of the ink.
   *Why:* tracing ink and fill together, as Potrace [6] does for one color or per-color tracers do, either swallows
   thin lines or leaves dark halos on every edge. Unmixing is the same idea as alpha matting, applied to a known
   foreground color. Since 1.7 the ink is treated as **strokes**, as line-drawing vectorization does [25, 26]: each
   stroke has its own ink color (up to three inks, so grey lines stay grey), and a dark part wider than a stroke
   that has shading of its own (a reflection on a black screen) stays a fill (§8.2).
2. **Segmentation into regions** (`regions.py`). An edge-preserving self-guided filter (He et al. [7]) removes noise.
   A fine palette in CIELAB gives initial regions, and a union–find over the adjacency graph merges neighbours **only
   if one gradient still explains the union**. *Why:* merging by color distance alone (as in Ardeco [8] and most
   tracers) cuts a soft shading into bands. Testing the merge with the fill model keeps one region per shaded
   object, while hard boundaries (two fabrics, a blush) stay. This is the same design question as
   Photo2ClipArt [9], answered with a cheaper greedy test instead of a global optimisation.
3. **Gradient fills** (`gradients.py`). Each region is a solid color, a linear gradient, or an elliptical radial
   gradient (it must fit 20 % better to be chosen). The stop colors are solved by least squares **against exactly
   what a browser draws** (piecewise-linear interpolation in sRGB), so a straight ramp is reproduced almost exactly.
   *Why:* SVG renderers support only these gradients. Gradient meshes [10] and diffusion curves [11] fit better but
   are not portable: SVG 2 mesh gradients are not implemented by browsers.
4. **Shared boundaries** (`planar.py`). Region borders become chains between junctions in a planar map. Every chain
   is fitted **once** and used by both neighbours. *Why:* fitting each region separately (the usual approach) leaves
   hairline gaps or overlaps between neighbours, which tracers hide with strokes. A shared map has none by
   construction.
5. **Sub-pixel edges** (`subpixel_offsets`). The position of an edge inside a pixel follows from its anti-aliased
   value, so boundaries are placed at fractions of a pixel instead of on the pixel grid. *Why:* this is most of what
   separates 98 % from 99.5 % on clean art (§4).
6. **Curve fitting** (`curves.py`). Each chain is smoothed, cut at sharp corners, and fitted with least-squares cubic
   Béziers within a maximum error (Schneider's algorithm [12]). The tolerance is relaxed where the outline layer
   covers the boundary (it is invisible there).
7. **Small pictures** (since 1.7): under 512 px on the long side, segmentation runs on a 2× grid made by
   nearest-neighbour enlargement. The coordinates are written back in source pixels. *Why:* text and lines of 1–2 px
   are then two to four grid cells wide and survive segmentation. Nearest-neighbour keeps the original anti-aliased
   values, so sub-pixel edges stay exact: Lanczos rings and bilinear blurs (measured in §5.2).

### 3.2 Flat engine

Its stages are load → background → k-means in CIELAB (k-means++ [13], fixed seed, automatic *k*) → **two-color mix
assignment** → majority filter and speck removal → shapes → shared contours at sub-pixel positions →
Douglas–Peucker [14] line detection, circle-fit arc test, line intersections for sharp corners, angle snapping →
Béziers for the curves → trimmed SVG. Since 1.7, a chain that is an ellipse or a circular arc becomes that exact
curve [27, 28], and a run is only a line if its residual is not a systematic bow (§8.2). The full description and
the parameters are in [logo-engine.md](logo-engine.md).

The decisive choice is the **assignment**. An anti-aliased edge pixel is a mix *t·A + (1 − t)·B* of two palette
colors. Taking the nearest palette color (what posterization does) makes thin shapes grow or shrink and creates
false third colors along edges. Projecting each pixel onto the closest *mix* and giving it the color that covers at
least half of it keeps every edge where it really is. Colors are compared with CIEDE2000 (Sharma et al. [15]), the
color difference closest to human judgement.

Pixel art is the exception: there every pixel is a deliberate square, so the engine follows the grid exactly instead
of smoothing it (unlike Kopf & Lischinski's depixelization [16], which reinterprets the art).

### 3.3 The optional AI step

A Real-ESRGAN model (Wang et al. [17]) can clean and enlarge the picture before tracing. It runs locally through
ONNX Runtime and is downloaded only on request (BSD-3-Clause weights). The vectorizer itself is unchanged: it simply
receives a sharper picture.

*Why it is there.* Many pictures people have are small or JPEG-compressed: blurred edges, ringing, 8×8 block noise.
Every stage above reads edges from pixel values, so damage is traced faithfully as damage. A super-resolution model
trained on synthetic degradations (blur, noise, JPEG) restores edges before tracing.

*Why it is optional and not the default.* Three reasons:

1. **The gain is conditional.** It helps on small or damaged pictures (§5.2) and does nothing measurable on large
   clean ones, which still cost 3× the time.
2. **A model can invent detail.** A generative restorer can add texture that was never in the picture. For a tool
   whose promise is fidelity, that must be the user's choice.
3. **Size and footprint.** 5–18 MB per model plus the onnxruntime package. The core stays a few MB.

The app's *Automatic* mode therefore applies it only where it was measured to help (long side < 1000 px, or JPEG
input). With the Logo style it applies it to JPEGs only: on small PNG logos the similarity did not improve in 8 of 8
measured cases and the visible-defect area was mixed (§5.2), but on 12 compressed logos (§5.7) it cut the
visible-defect area from a median 0.53 % to 0.02 % (shop icon at JPEG quality 30: 5.2 % → 0.28 %), for a mixed
similarity (−0.8 to +0.4 points). Never with Pixel art, whose every pixel is meant. *Always* still applies it.

*Why not a model that writes SVG directly* (StarVector [4] and other LLM-based generators)? They are trained mostly
on icons, emoji, diagrams and fonts, need a GPU and billions of parameters, and their authors report them as best on
those domains, not on detailed illustrations or natural images. Their output also changes from run to run. A deterministic tracer with a small, optional restoration
step fits the goals of §1 better.

## 4. How quality is measured — and what "99.9 %" means

**Similarity** (the score in the app, `pngsvg.compare.similarity`) is 100 − the mean absolute RGB error in percent,
between the SVG rendered by headless Chrome/Edge at the picture's size and the picture flattened on white. It is
simple, has no parameters, and every user can check it. Its limits are known and reported with it:

- **It is dominated by edges.** Inside a flat area the error is near zero; nearly all error sits on the 1–2 px
  anti-aliased band along edges, where the SVG renderer's anti-aliasing never matches the original exactly. The
  benchmark therefore also reports *similarity away from edges* and the *share of the error on edge pixels*.
- **It depends on size.** A small picture has proportionally more edge pixels, so the same tracing quality scores
  lower (the 235 px icon in §7.2 is 98–99 %; the same kind of art at 1280 px is 99.8 %+).
- **99.9 % means a mean error of 0.26 levels of 255 per channel.** That is below what anyone can see, and close to
  the difference between two browsers rendering the *same* SVG. For flat art with edges it is the practical ceiling,
  not a typical result.
- **Pixel metrics are not perception.** We also report **PSNR** and **SSIM** (Wang et al. [18]), the standard
  structural metric. LPIPS [19] and DINO-based scores used in learned vectorization papers [4, 5] need neural
  networks and are not used here.

**A high similarity can hide a visible defect.** This is the most important lesson of this report. In 1.6.0, a
flat shop icon whose red and blue shades had merged scored 97.99 %. A Tux icon whose thick grey rim had merged into
black scored 97.65 %. Both look wrong at first sight. The mean error is small because the defect covers a few
percent of the pixels and the rest is exact. Three measures address this:

- **Visible-defect area** (`pngsvg.compare.defect_area`): the share of the picture where the SVG differs from the
  source by more than CIEDE2000 5 (clearly visible side by side), after a 3×3 morphological opening. The opening
  removes the 1–2 px lines along edges, where anti-aliasing never matches exactly. It does not average: a merged
  color shows up as its full area. The shop icon above had 18.33 % defects, the Tux icon 10.22 %. After the fixes of
  §7 they have 0.00 % and 0.01 %. Its blind spot is defects thinner than 3 px.
- **Pictures** of every result next to its source, with the defects in red and the worst area enlarged
  (`bench/evidence.py`). The README shows them.
- **A vision-language model as a second pair of eyes** (`bench/judge.py`, §5.4). It describes the defects it sees
  and scores the result 0–10. LLM-as-a-judge methods are known to be biased and inconsistent (Zheng et al. [21]),
  so the judge is calibrated with control pairs whose answer is known (identical pictures, pictures damaged on
  purpose), every pair is judged three times, and its agreement with the pixel metrics is reported.

**Simplicity** is reported as SVG size and path count, and **speed** as seconds on one CPU process.

## 5. Results

### 5.1 Two sets, every picture

45 license-free pictures from Wikimedia Commons, all of them used: **E7** (27) are renders of CC0 vector art, the
cleanest possible input, plus three photos and paintings; **E8** (18) were made as rasters: PNGs from 300 px, JPEG
clipart, pixel art, glossy icons, a 3D render and a photo-like clipart. Each picture gets the style a user would
pick for its kind; Logo and Pixel art keep an opaque picture's background (removing it is a choice, not an error).
Full per-picture tables: the README and `bench/results/readme.md`.

| Set | Group | Images | Median similarity | Median defect area | Worst defect area | Median SSIM | Median size |
|---|---|---|---|---|---|---|---|
| E7 | flat art (icons, flags, flat, cartoon, pixel) | 24 | 99.81% | 0.05% | 0.89% | 0.993 | 38 KB |
| E7 | photos, paintings, 3D renders | 3 | 92.73% | 22.39% | 49.22% | 0.472 | 538 KB |
| E8 | flat art (icons, flags, flat, cartoon, pixel) | 16 | 99.40% | 0.34% | 11.46% | 0.981 | 27 KB |
| E8 | photos, paintings, 3D renders | 2 | 97.08% | 7.58% | 9.37% | 0.894 | 68 KB |

On flat art the median result has 99.4–99.8 % similarity **and** 0.05–0.34 % visible defects, which in the pictures
means scattered edge pixels; on the renders of vector art (E7) no flat-art picture is above 0.9 %. The worst cases of
E8 are a gradient forced into the Logo style (11.5 %, with a warning) and a scanned marker drawing whose textured
dark-red outlines become black ink (6.8 %). A dark-grey reflection on a black screen, taken for ink before the
changes of §8.2 (5.6 %), is now 0.03 %. Photos and paintings remain out of reach (§7.4).

### 5.2 Small pictures and the AI step

Ten E7 pictures shrunk to 256 px. Cells: similarity · visible-defect area · size.

| Image (256 px) | Style | 1× grid (before 1.7) | 2× grid (default) | AI + 2× |
|---|---|---|---|---|
| astronaut | Cartoon | 97.05% · 0.72% · 11 KB | 97.52% · 0.80% · 25 KB | 97.68% · 0.15% · 15 KB |
| cow | Cartoon | 97.67% · 1.04% · 17 KB | 98.16% · 0.79% · 24 KB | 98.76% · 0.10% · 14 KB |
| penguin | Cartoon | 97.64% · 1.47% · 33 KB | 97.99% · 1.19% · 46 KB | 98.38% · 0.89% · 39 KB |
| fish-mascot | Cartoon | 97.49% · 4.15% · 5.4 KB | 98.45% · 1.59% · 12 KB | 98.23% · 0.75% · 7.2 KB |
| shipment | Flat illustration | 97.52% · 5.38% · 18 KB | 98.07% · 3.79% · 35 KB | 98.57% · 1.36% · 25 KB |
| flag-nepal | Logo | 99.01% · 0.00% · 2.0 KB | 99.01% · 0.00% · 2.0 KB | 98.68% · 0.00% · 1.9 KB |
| flag-south-africa | Logo | 99.24% · 0.00% · 0.8 KB | 99.24% · 0.00% · 0.8 KB | 99.21% · 0.00% · 0.8 KB |
| icon-shop | Logo | 98.25% · 4.01% · 5.7 KB | 98.25% · 4.01% · 5.7 KB | 97.91% · 0.46% · 11 KB |
| icon-flask | Logo | 99.77% · 0.06% · 1.1 KB | 99.77% · 0.06% · 1.1 KB | 99.47% · 1.06% · 3.3 KB |
| icon-cat | Logo | 99.63% · 0.09% · 0.6 KB | 99.63% · 0.09% · 0.6 KB | 99.55% · 0.00% · 0.8 KB |
| **median, Cartoon / Flat** | | **97.52% · 1.47%** | **98.07% · 1.19%** | **98.38% · 0.75%** |
| **median, Logo** | | **99.24% · 0.06%** | **99.24% · 0.06%** | **99.21% · 0.00%** |

For cartoons and flat illustrations, the 2× grid (§3.1 step 7) lowers the median defect area from 3.24 % to 1.15 %
and the AI step to 0.47 %, with smaller files than the 2× grid alone. This is the measured justification of §3.3.
For logos, neither helps measurably, so the AI step is not applied automatically there.

### 5.3 Before and after: the errors of §7 on the same pictures

1.6.0 and this version, each in its own process, same inputs, scored the same way (`bench/before_after.py`).

| Case | 1.6.0 similarity · defects | Now similarity · defects | Size 1.6.0 → now |
|---|---|---|---|
| Flat icon, Logo style: a color and its darker shade | 97.99 % · 18.33 % | **99.95 % · 0.00 %** | 5.3 → 6.2 KB |
| Flag, Logo style (background kept): a color on 0.7 % of the picture | 99.08 % · 0.52 % | **99.89 % · 0.01 %** | 1.7 → 18.2 KB |
| Flat icon, Logo style: a grey between black and white | 97.65 % · 10.22 % | **99.77 % · 0.01 %** | 3.7 → 4.9 KB |
| Pixel art (background kept): checkerboard and 1-pixel details | 97.58 % · 16.26 % | **100.00 % · 0.00 %** | 3.3 → 14.5 KB |
| Line drawing, Logo style: a 3 px ring (1.6 cut it at every thin spot) | 98.89 % · 0.36 % | **99.62 % · 0.00 %** | 6.5 → 2.2 KB |
| Cartoon style: a grey reflection on a black screen (1.6: ink) | 99.11 % · 5.63 % | **99.61 % · 0.03 %** | 18.8 → 24.0 KB |
| Opaque dark picture, Logo style | 84.28 % · 25.95 % | **98.13 % · 0.94 %** | 164.1 → 29.4 KB |
| Thin bars (4-12 px), Logo style | 94.92 % · 6.83 % | **100.00 % · 0.00 %** | 0.4 → 0.4 KB |
| Small picture (256 px), Cartoon style | 97.67 % · 1.04 % | **98.16 % · 0.79 %** | 17.2 → 23.9 KB |

### 5.4 A vision model as a second pair of eyes

The pixel scores say how much differs, not whether a person would notice. So every result was also shown to
a vision-language model (**nvidia/nemotron-3.5-super-vl-120b-a12b**, NVIDIA NIM), next to its source with the worst area enlarged, and it was
asked to list the defects it sees and to score the copy 0–10 (3 runs per pair, temperature
0.3; prompt and answers in `bench/results/judge.json`).

**Is the judge trustworthy?** It was first given pairs with a known answer:

| Control pair | Expected | Scores (3 runs) |
|---|---|---|
| identical: `cow` | identical (expect 10) | 10, 10, 10 |
| identical: `tux-flat` | identical (expect 10) | 10, 10, 10 |
| identical: `starry-night` | identical (expect 10) | 9, 8, 9 |
| erased: `icon-shop` | a part erased (expect <= 5) | 4, 4, 4 |
| hue: `border-collie` | colors shifted (expect <= 5) | 4, 6, 6 |
| posterized: `shipment` | 3 colors per channel (expect <= 6) | 4, 4, 4 |

**Results** (median of the runs; 10 = no visible difference, 8–9 = only in the enlargement):

| Set | Group | Pictures | Median score | Lowest | Scored 9 or 10 |
|---|---|---|---|---|---|
| E7 | flat art | 24 | 9 | 6 | 18 of 24 |
| E7 | photos, paintings, renders | 3 | 4 | 4 | 0 of 3 |
| E8 | flat art | 16 | 9 | 7 | 13 of 16 |
| E8 | photos, paintings, renders | 2 | 5 | 3 | 0 of 2 |

**What it adds.** Over all pictures its ranking agrees with the pixel metrics about equally (Spearman: similarity
0.67, SSIM 0.697, visible-defect area 0.679); on flat art alone the agreement is
moderate (0.529, 0.567, 0.543). So no single number replaces looking.
What the judge adds is *naming* small details that matter to a person but cover few pixels. In the first run it
scored the Brazilian flag 4/10 for its missing stars and motto, while the visible-defect area was only 0.52 % (that
metric ignores details under 3 px). This led to a fix (smaller speck limit in the Logo style, technical report
§7.3); the flag now scores 8/10. It also confirmed the other fixes: a line drawing whose ring 1.6 cut into pieces scores
10/10, the robot whose grey pupil had turned black 9/10. It still names the feather lines of a flag's bird (6/10). Its runs agreed closely (median spread 0 points; every answer was valid).
The pictures it scored 7 or lower, and why:

| Picture | Judge | Similarity | Defect area | What the judge saw (first run) |
|---|---|---|---|---|
| E8 `saxophone` | 3 | 95.65 % | 9.37 % | Staff lines broken into disconnected fragments; Musical notes distorted into grey blobs |
| E7 `great-wave` | 4 | 92.73 % | 22.39 % | Lost fine details in the boat structure and figures; Merged water colors and lost foam texture |
| E7 `starry-night` | 4 | 92.17 % | 49.22 % | Lost fine brushstroke texture and detail; Colors merged into large flat regions |
| E7 `earth-apollo17` | 4 | 95.18 % | 15.23 % | Fine cloud and ocean textures replaced by large flat color regions; Smooth gradients posterized into stepped bands |
| E7 `flag-kiribati` | 6 | 99.49 % | 0.26 % | Missing internal feather texture lines on the bird; Stray blue pixel artifacts on the bird |
| E8 `kaskelix` | 7 | 97.91 % | 11.46 % | Slight color/gradient mismatch on the rear body (darker patch in B); Minor outline artifact/irregularity visible in the enlarged area |
| E8 `spot-cow` | 7 | 98.51 % | 5.79 % | blocky gradients instead of smooth shading; faceted surfaces instead of smooth curves |

The judge has known weaknesses (Zheng et al. [21]): it can miss small things, it sometimes names a defect that is
not there, and its scores move by a point between runs. It is used here as a second pair of eyes, next to the
pixel metrics and the pictures, not instead of them. The app never sends pictures anywhere.

### 5.5 Other open-source tracers on the same pictures

The same 45 pictures, rendered and scored the same way, through two widely used open-source tracers with documented
settings and no per-picture tuning (`bench/compare_tools.py`):

- **VTracer** 0.6.15 (visioncortex [35], MIT): its defaults, and its high-detail settings ("fine": color precision
  8, layer difference 8, speckle filter 2).
- **Potrace** (Selinger [6]) traces black and white only. Colors are traced the way Inkscape's multi-color *Trace
  Bitmap* does: 8 colors (median cut), each traced as the union of itself and the colors drawn after it, stacked.
  The pure-Python port `potracer` 0.0.4 was used, so its times are not those of the C program.

| Tool | Median similarity | Median defect area | Median size | Median paths | Median time |
|---|---|---|---|---|---|
| **this project** (style per kind) | **99.57 %** | **0.17 %** | **41 KB** | 49 | 6.1 s |
| VTracer, defaults | 98.90 % | 0.40 % | 143 KB | 75 | 0.28 s |
| VTracer, fine | 99.03 % | 0.19 % | 219 KB | 167 | 0.32 s |
| Potrace, 8 colors stacked | 98.13 % | 9.54 % | 307 KB | 7 | (Python port) |

What the table means, without spin:

- **Fidelity and size.** On flat art (40 pictures) this project scores higher than VTracer-fine on 38, with files
  that are a median 166 KB smaller (5.7× smaller); §5.6 gives the statistics. Potrace's 8 stacked colors miss the
  colors that the quantization drops (a median 7 % of flat art visibly wrong).
- **Where VTracer is better.** VTracer-fine has the smaller visible-defect area on 15 pictures, 12 of them by more than 0.05 points: the 5 photos,
  paintings and renders (e.g. starry-night 13 % vs. 49 %), and 7 shaded or textured cartoons and flat
  illustrations (border-collie 0.83 % vs. 1.05 %,
  running-collie 0.20 % vs. 0.98 %, mustache-guy 0.14 % vs. 0.95 %). Its many small layers copy texture and shading
  closely; it pays with 3–5× larger files, more paths and lower similarity on the same pictures (98.15 % vs. 99.14 %
  on border-collie): its stacked layers shift edges and leave halos that are too small for the defect metric but
  add up in the mean error.
- **Speed.** VTracer (Rust) is about 20× faster. This project spends its time on sub-pixel edges, gradient fits and
  curve fitting, and stays within seconds on a laptop.

### 5.6 Is the difference real? Paired statistics

Every comparison is on the same pictures, so it is *paired*: the pictures differ far more from each other than the
methods do. Per metric: the median of the per-picture differences with a bootstrap 95 % confidence interval (Efron &
Tibshirani [45], 10 000 resamples, fixed seed), wins / ties / losses, the two-sided Wilcoxon signed-rank test
(Wilcoxon [43], Pratt's treatment of zero differences) and the matched-pairs rank-biserial correlation as effect size
(Kerby [44]: −1 to 1, positive = this version better). Script: `bench/stats.py`; all tables: `bench/results/stats.md`.

All 45 pictures:

| Comparison | Metric | Other (median) | This (median) | Median gain [95 % CI] | Wins / ties / losses | p | r |
|---|---|---|---|---|---|---|---|
| vs. 1.6.0 | similarity | 99.29 % | 99.57 % | +0.00 [+0.00, +0.05] | 21 / 24 / 0 | 4.0e-06 | +1.00 |
| vs. 1.6.0 | defect area | 0.52 % | 0.17 % | +0.00 [+0.00, +0.00] | 15 / 28 / 2 | 2.7e-04 | +0.80 |
| vs. 1.6.0 | size | 40.3 KB | 40.9 KB | +0.0 KB [+0.0, +0.0] | 6 / 23 / 16 | 0.017 | −0.64 |
| vs. VTracer-fine | similarity | 99.03 % | 99.57 % | +0.45 [+0.38, +0.57] | 38 / 1 / 6 | 5.8e-04 | +0.58 |
| vs. VTracer-fine | defect area | 0.19 % | 0.17 % | +0.03 [−0.01, +0.13] | 24 / 6 / 15 | 0.31 | +0.18 |
| vs. VTracer-fine | size | 219 KB | 41 KB | +187 KB [+119, +570] | 45 / 0 / 0 | 5.7e-14 | +1.00 |
| vs. Potrace-8 | similarity | 98.13 % | 99.57 % | +0.91 [+0.40, +1.42] | 39 / 1 / 5 | 1.5e-08 | +0.87 |
| vs. Potrace-8 | defect area | 9.54 % | 0.17 % | +6.78 [+2.77, +13.87] | 38 / 5 / 2 | 5.3e-08 | +0.95 |

Reading it:

- **1.7 vs. 1.6.0.** The changes hit specific pictures and leave the rest identical (24 of 45 ties in similarity),
  so the *median* gain is 0 while *no picture got worse in similarity* and only 2 got slightly worse in defect area:
  the improvement is real (p < 0.001) and concentrated where 1.6 failed (§5.3). Files grew on 16 pictures, the
  price of colors and shapes that are no longer dropped.
- **vs. VTracer.** Higher similarity and 5× smaller files are clear on any picture set. The visible-defect area is
  *not* significantly different over all 45 pictures (p = 0.31): on flat art alone it is (p = 0.012, 24 wins / 10
  losses), on shaded cartoons and photos VTracer is often better (§5.5). Claims in the README stay within this.
- **vs. Potrace with stacked colors**: better on every metric with large effects; mostly a statement about color
  quantization before binary tracing.

### 5.7 Damaged input

Real pictures are compressed, shrunk and noisy. Ten flat-art pictures of both sets were damaged three ways at three
strengths, JPEG compression (quality 70 / 50 / 30), down-scaling (bicubic) and Gaussian noise (σ 4 / 8 / 16 levels),
the way recent work tests vectorizers on real-world input (VectorArk [40]). Every SVG is rendered at the *original*
size and compared with the *clean* original: a good score means the picture was recovered, not that its damage was
copied (`bench/robustness.py`). Medians over the ten pictures (similarity · visible-defect area):

| Damage | this project | this project + AI | VTracer |
|---|---|---|---|
| none | 99.69 % · 0.10 % | 99.38 % · 0.04 % | 99.00 % · 0.14 % |
| JPEG q70 | 99.51 % · 0.34 % | 99.37 % · 0.06 % | 98.92 % · 0.90 % |
| JPEG q50 | 99.28 % · 0.81 % | 99.36 % · 0.07 % | 98.74 % · 1.36 % |
| JPEG q30 | 99.25 % · 1.14 % | 99.33 % · 0.06 % | 98.73 % · 1.86 % |
| scaled ×0.75 | 99.42 % · 0.38 % | 99.30 % · 0.29 % | 98.74 % · 0.21 % |
| scaled ×0.5 | 99.11 % · 1.46 % | 99.17 % · 0.67 % | 98.33 % · 0.82 % |
| scaled ×0.25 | 98.14 % · 5.64 % | 98.45 % · 2.18 % | 97.30 % · 3.91 % |
| noise σ 4 | 99.07 % · 0.20 % | 99.37 % · 0.04 % | 98.54 % · 0.44 % |
| noise σ 8 | 98.61 % · 0.25 % | 99.27 % · 0.03 % | 98.25 % · 0.57 % |
| noise σ 16 | 97.83 % · 0.41 % | 99.01 % · 0.11 % | 97.27 % · 5.17 % |

- **This project degrades gracefully** and stays above VTracer in similarity under every damage, and below it in
  visible defects under JPEG and noise (σ 16: 0.41 % vs. 5.17 %). Down-scaling is the exception: there
  VTracer has fewer visible defects (0.82 % vs. 1.46 % at 50 %), because fewer pixels cannot hold 1–2 px details and
  its many small layers follow the blur more closely.
- **The AI step pays off on damaged input**: under JPEG and noise it keeps the visible defects at 0.03–0.11 %, and on
  pictures shrunk to 25 % it halves them (5.64 % → 2.18 %). On clean input it does not help the similarity (§3.3).
- **The Logo style before the fixes of §7.3 and §8.2** collapsed under noise: on the four logos of this test,
  σ 16 gave a median 90.55 % with 32.4 % visible defects (a flag 83 %, 37 %); now 98.29 % and 0.15 %. The same logos
  clean: 99.56 % → 99.80 %, worst defect area 10.4 % → 0.38 % (the shop icon on its white page, §7.3).

## 6. Reproduce

```bash
pip install -e ".[dev]"
python bench/fetch_sets.py && python bench/fetch_sets.py --set real   # 27 + 18 CC0 / public-domain pictures
python bench/readme.py --models MODELS_DIR     # §5.1, §5.2 -> bench/results/readme.md (models: the models-v1 release)
python bench/evidence.py                       # the pictures in docs/images/evidence
mkdir old && git archive v1.6.0 src | tar -x -C old && python bench/before_after.py --old old   # §5.3
NVIDIA_API_KEY=... python bench/judge.py       # §5.4, optional (a free key from build.nvidia.com)
pip install vtracer==0.6.15 potracer==0.0.4 && python bench/compare_tools.py   # §5.5 (benchmark only)
python bench/versions.py --old old && python bench/stats.py                   # §5.6
python bench/robustness.py --models MODELS_DIR                                 # §5.7
python bench/ai_restore.py MODELS_DIR --limit 10   # the restoration test of docs/bench.md (v1.3)
pytest -q
```

Chrome or Edge must be installed (rendering). Results differ in the second decimal between browser versions.

## 7. Known errors and limitations

### 7.1 Fixed: the logo style hollowed paintings (found in 1.6.0, fixed in 1.7)

*Symptom.* A 1713×918 painting (a dark night scene) vectorized with the **Logo** style came out with large
transparent holes: 80.19 % similarity and **59.6 %** visible-defect area, against 96.9 % with the Cartoon style.

*Root cause.* In `logo.assign` the background color was always one of the candidate colors for the two-color mix,
**even when no background had been detected**. On this picture no border color dominates, so nothing was marked as
background, but the dominant dark border color was still offered as a candidate. Every pixel of that dark color,
anywhere in the picture, was labelled "background" and left out of the SVG. A second, related weakness: when a
border color *does* dominate, it was removed even on pictures the engine itself had just flagged as not flat.

*Fix.* The background takes part in the assignment only if there is one. If the background was guessed from the
border and the picture is not flat, it is kept, with a note to the user. Result on the same painting: **94.38 %**,
no holes (the remaining 33 % defect area is what 16 flat colors cannot show of a painting; Cartoon: 12.9 %). Two regression tests (`tests/test_logo.py`) fail on 1.6.0 and pass now. The Logo style is still the
wrong choice for a painting (16 flat colors at most): the app says so and suggests Cartoon.

### 7.2 Improved: small icons with text

*Symptom.* A 235×215 icon with a word under it: 98.45 % with Cartoon (1.94 % visible defects). The error map showed 46 % of the error in
the text rows, 25 % on edges, and only 30 % in the flat interior.

*Root cause.* Letter strokes 1–2 px wide cannot be represented by region boundaries on the pixel grid. Lowering the
region-size thresholds changed nothing (98.47 %), so it is resolution, not tuning.

*Fix.* The 2× grid of §3.1 step 7: **99.03 %** and 1.22 % defects without AI, close to the 99.19 % reached with
the AI step, in 0.7 s. Curve tolerances stay in source pixels on the finer grid, so the file grows only from 9 to
12 KB. The Logo style on the same icon: 98.22 % / 6.77 % → 99.11 % / 1.76 % (§7.3).

### 7.3 Fixed: the logo style merged two shades of one hue, lost small colors and flattened thin bars

These were found while building the benchmark of §5. All are in `logo.py`, and each has a test that fails on 1.6.0.

| Error in 1.6.0 | Root cause | Fix | Example |
|---|---|---|---|
| A flat UI icon lost half of its colors (red / dark red, blue / dark blue: CIEDE2000 8.6–10 apart) | the automatic number of colors stopped as soon as the *mean* error was small; a merged shade pair is a small share of all pixels | also require 99.8 % of the flat pixels to be within 4 ΔE of their color; up to 16 colors; merge only clusters closer than 7 | icon-shop 97.99 % → **99.95 %**, visible defects 18.33 % → 0.00 % (6 → 10 colors, the exact palette) |
| A flag's white band became a hole, even with the background kept (it looks white only on a white page) | the background color was a candidate for every pixel (§7.1), and white covers only 0.7 % of the flag, below what the mean-error criterion notices | §7.1 and the 99.8 % tail criterion: the band is a white shape | flag-brazil: the band is back (99.08 % → 99.61 %) |
| A thin straight bar (4–8 px wide) became a zero-area sliver | two long sides separated by a short gap were always joined at one corner. Parallel lines have no intersection, so both ends fell back to the midpoint of the short side | parallel neighbours keep the short side between them, as a line (square end) or as a curve (rounded end) | `M244 0h-8V221h8Z` instead of `M239.5 0l1 221Z`; four bars: 94.92 % → 100.00 % |
| Light halos of an older trace became a third color once colors were counted correctly | rims of a near-background color hugging other shapes | such rims (90 % within 5 px of their edge, ≥ 30 % of their outline against other shapes) return to the background; a light line on its own stays | Turion logo, degraded fixture: 2 colors, 3 paths, 99.30 % → 99.44 % |

The second benchmark set (E8, pictures made as rasters), the visible-defect metric and the vision judge (§5.4) then
exposed four more:

| Error in 1.6.0 | Root cause | Fix | Example |
|---|---|---|---|
| A flat grey rim merged into the black beside it | in the two-color mix assignment, a pure grey lies exactly on the black–white mix line: residual 0, like the pure color, and the pair came first | a pixel takes its nearest pure color unless a mix is clearly better (8 levels) | Tux icon: 97.65 % / **10.22 %** defects → 99.72 % / 0.01 % |
| Pixel art lost colors (a checkerboard turned black) and a white swan became a hole | the palette is sampled from "flat" pixels, those whose neighbours have the same color: in pixel art a checkerboard or a 1-pixel line has none | Pixel art takes its colors exactly (up to 64), and keeps single pixels | bird sprites (background kept): 97.58 % / **16.26 %** defects → **100.000 %** / 0 % |
| The stars and the motto of a flag were dropped | specks were pieces under 0.05 % of the artwork (570 px on a 1280 px flag): far above noise, which the majority filter and the minimum area already remove | 0.003 %; JPEG logos gain 1–2 paths at most | flag-brazil 99.61 % → 99.84 %, defects 0.52 % → 0.07 %; the vision judge had scored it 4/10 for exactly this |
| Line art was called "not a flat logo"; some paintings were not | the shading check measured every pixel against the nearest pure color, and anti-aliased lines are mostly mixes | measure against colors **and their mixes**; a gradient cut into bands is found by its false edges (borders through smooth color) | line drawing: no note; a shaded whale icon now gets one |

A noisy JPEG never meets the 99.8 % criterion (ringing is not a color). The search therefore stops when two more
clusters no longer reduce the tail by 10 %, and the "not a flat logo" note appears only when the mean error is
large.

The damaged-input test (§5.7) then exposed two more, both in pictures a user is likely to have:

| Error in 1.6.0 | Root cause | Fix | Example |
|---|---|---|---|
| An icon on an opaque white page, background kept, lost 3 of its 10 colors | the white page was most of the k-means sample and pulled the clusters: two reds became one, a light grey (#ECF0F1) became white | quantize the art without the guessed background, add the background color, merge colors within 7 ΔE into it (JPEG rims), and add a light color close to it only when its flat pixels form a second peak in the distance to the background | shop icon on white: 97.75 % / **10.42 %** defects → 99.96 % / 0.00 %; Tux JPEG q70 0.39 % → 0.03 % |
| Noise (a scan, a photo of a print) broke the Logo style: a flag under noise σ = 16 had 37 % visibly wrong | flat pixels are found by "no neighbour differs by more than 12 levels", so under noise there are none, and every pixel becomes its own little shape | estimate the noise from the picture; from 1.5 levels, smooth it with an edge-preserving filter first (§8.2) | flag-nepal σ 16: 83.04 % / 36.7 % → 98.53 % / 0.00 %; §5.7 |

Smoothing has one side effect, caught by the before/after test of §5.3: on a textured painting it removes the texture
like noise, the border color becomes dominant and is taken for a background, and only the later gradient check
notices that the picture is not flat. That check now keeps a guessed background too, exactly like the shading check
(§7.1): the dark night picture of §5.3 went from 97.83 % / 6.66 % to 98.13 % / 0.94 % instead of to 70.8 % with holes
(test: a textured gradient keeps its border color).

### 7.4 Open limitations

- **Photos and paintings.** Continuous texture has no regions to find: the SVG approximates it with hundreds of
  shapes (94–97 %, 0.5–1.2 MB). Optimisation methods [2, 3] do better, but in minutes on a GPU. For such pictures an
  SVG is rarely the right format.
- **Full-bleed flat art in the Logo style.** On a flag or app icon whose border color is part of the design, that
  color is taken as the background. Switch off *Transparent background*.
- **Background-like colors in the Logo style.** Without transparency and with *Transparent background* on, every
  pixel within 6 ΔE of the border color is background, also inside the art: a #ECF0F1 shape on white becomes a hole
  (invisible on white, visible on a dark page). Transparent PNGs, and the background kept (§7.3), do not have this
  problem.
- **Lines of 1–2 px in a color used nowhere else** (Logo style, pictures over 256 px) are lost: every one of their
  pixels touches another color, so none is sampled for the palette.
- **Gradients.** Only what SVG renderers support (linear, radial). Strongly non-linear shading shows soft bands.
- **Very thin hairlines** (< 1.5 px, mostly anti-aliasing) on large pictures can be lost; one ink color per picture,
  and dark colors close to it (a dark-grey reflection on black, dark-red marker lines) are taken for ink.
- **The metric.** Similarity rewards matching pixels, not good drawing: a tracer that copies JPEG noise faithfully
  scores well and produces a bad file. Always look at the result at 2× zoom.

## 8. Improvements from the literature (1.7), and what did not work

After the benchmark of §5 existed, each stage was compared with the research closest to it, the most promising
ideas were implemented, and **each was kept only if it measurably improved the benchmark without making other
pictures worse**. Negative results are reported too: they show where an idea does not fit this pipeline.

### 8.1 Where does the Logo style lose accuracy? An error decomposition

A vectorizer has two places to lose accuracy: *estimating* where an edge is, and *fitting* curves to that estimate.
To separate them, the sub-pixel boundary polylines (§3.2, after anti-aliasing analysis) were written to the SVG
directly, as straight segments through every point, without any fitting. This is a bound on what fitting can reach.

| Picture | Fitted (1.6 fitting) | Polyline bound | Fitting loss |
|---|---|---|---|
| Ferris (crab icon) | 99.33 % | 99.80 % | 0.47 |
| evil-twin (line drawing) | 99.12 % | 99.76 % | 0.64 |
| Tux icon | 99.72 % | 99.87 % | 0.15 |
| Brazilian flag | 99.84 % | 99.92 % | 0.08 |
| shop icon | 99.95 % | 99.98 % | 0.03 |

The edge estimate already reaches 99.8–99.98 %, so **99.9 % is reachable on flat art, and the loss is in fitting**.
Smoothing before the fit was not the cause (σ = 1 → 0: ±0.02). Switching single steps off pointed at two culprits:
accepting gently curved runs as straight lines (+0.21 / +0.36 without line detection), and, as the pictures then
showed, a shape-splitting bug.

### 8.2 Kept

| Change | Grounded in | Result on the benchmark |
|---|---|---|
| **A stroke is not a chain of necks.** A one-color piece is split at a thin neck only between thick parts of ≥ 64 px; a piece that is mostly thin (a ring, a line) stays whole. 1.6 cut a 3 px ring into dozens of shapes. | bug, found through §8.1 | evil-twin 99.12 % → 99.55 %, 31 → 9 paths, 6.7 → 3.6 KB; flag stars no longer split |
| **The bow test.** A run within the line tolerance is still a curve when its residual is *systematic*: a parabola explains more than 60 % of it and bulges more than 0.25 px. A straight but noisy edge has a random residual and stays a line. | lack-of-fit analysis of residuals; the "regularity" principle of PolyFit [24] | Ferris +0.11, Kiribati +0.05, whale +0.07; sizes unchanged; the degraded fixture stays clean |
| **Exact conics.** A closed chain within 0.8 px of an ellipse (direct least squares [27], in the numerically stable form [28]) becomes that ellipse; an open chain within 0.8 px of a circular arc through both of its ends (a one-parameter least-squares fit that keeps the shared junction points) becomes that arc. | Fitzgibbon et al. [27], Halíř & Flusser [28]; regularity in PolyFit [24] | evil-twin +0.07, Tux +0.03, exclamation icon 1.6 → 0.8 KB; no picture worse |
| **Ink is a stroke, and each stroke has its ink.** (Cartoon style.) Parts of the ink core wider than 24 px *with shading of their own* (more than 10 % of their pixels off the ink color) are dark areas and stay fills; a flat black area stays ink. Every stroke takes the median color of its darkest half, and strokes clearly different from the main ink (ΔE ≥ 15) form up to two more ink layers. | line-drawing vectorization treats ink as strokes with width and color [25, 26] | 32 Cartoon / Flat / Poster pictures: 6 better, 0 worse; median defect area 0.49 % → 0.31 %; total size +0.8 %. futuristic-mascot 5.63 % → 0.03 %, fish-mascot 1.66 % → 0.17 %, robot 1.24 % → 0.23 % |

| **Noise-aware smoothing** (Logo style). The noise level is estimated from the picture with Immerkær's 3×3 kernel, which is zero on flat color and on any linear ramp, taking the *median* of its absolute response instead of the mean, as in the median-absolute-deviation estimator of Donoho & Johnstone: edges are a minority of flat art, so a clean logo scores exactly 0 (all 13 flat-engine pictures of §5.1 do). From 1.5 levels, a bilateral filter (radius 2 px, color scale 3σ) smooths it before anything else, twice from σ ≥ 6. The noise left (from the filter weights, √Σw²/Σw, and √2 less for the second pass) raises the shading check's tolerance, so a denoised flag is not called "shaded". | Immerkær [46], Donoho & Johnstone [47], Tomasi & Manduchi [48] | 9 logos under noise σ 4 / 8 / 16 (§8.3 for the variants): median defect area 0.02 / 0.42 / 11.6 % → 0.00 / 0.00 / 0.30 %, worst 15.4 / 17.8 / 63.3 % → 0.6 / 0.6 / 10.6 %; clean pictures byte-identical |
| **Palette with a kept background** (Logo style): see §7.3. | bug, found through §5.7 | shop icon (background kept) 97.75 % → 99.96 %, flask 99.01 % → 99.96 %; clean pictures of §5.1 byte-identical |

### 8.3 Tried and not kept

| Idea | Grounded in | Result | Why not |
|---|---|---|---|
| **Fidelity guard**: refit any run whose Hausdorff distance to the sub-pixel polyline exceeds 0.6 px | direct optimization of shapes against the data, Yang et al. [22] | +0.02 to +0.24 points, depending on the variant | files 1.5–2.5× larger (10× on a logo with wavy edges, whose waves it reproduced while the engine is meant to straighten them: fidelity vs. simplicity, Favreau et al. [25]) |
| **Coverage partition on a 2× grid**: an anti-aliased pixel gives round(4t) of its sub-pixels to the color covering it | Subpixel Deblurring of Anti-Aliased Clip Art, Yang et al. [23] | Brazilian flag +0.03, evil-twin +0.06, but Tux −0.24, Ferris −0.09 | our continuous sub-pixel offsets already place smooth edges better than a 0.5 px partition; 3× slower, 2–4× larger. It helps only the topology of tiny details |
| **Plain 2× grid** (Lanczos) for every size | — | Tux −0.15, whale −0.5 | Lanczos rings at edges (as in the region engine, §3.1 step 7) |
| **Corners from the intermediate polygon** (sharp Douglas–Peucker vertices split curves) | PolyFit [24] | Ferris ±0; flag +0.01 for +30 % size | the lost tips were not in curve runs |
| **Ridge rescue**: a mixed pixel that is a local maximum of a color's coverage along an axis takes that color (a 1 px line would otherwise vanish), and the majority filter spares it | the sub-pixel partition above, applied only where 1× topology breaks | every logo slightly worse (Tux −0.12, Kiribati −0.09), thin test lines unchanged | the thin colors were not lost there (next rows) |
| **Unexplained colors join the palette**: pixels that are neither a palette color nor a mix of two, when few and compact, add their color | — | no change on any picture | the thin lines' colors were already in the palette |
| **No majority filter** | — | ±0.03 | not the cause either |
| **Incremental palette search**: keep the clusters of k − 1 and seed the new one at the mode of the badly explained pixels, instead of a fresh k-means++ per k | split-the-worst seeding, as in Linde–Buzo–Gray vector quantization; Celebi [30] on k-means initialization for color quantization | shop icon, background kept: 10.4 % → 4.5 % defects, but the same icon with the background removed 0.00 % → 4.5 %, and noisy flags far worse | it fixes the symptom; the cause was the background in the sample (§7.3) |
| **Smoothing only for the palette**, or for the palette and the labels (raw pixels for the sub-pixel edges) | — | same as smoothing everything on σ 16; worse on σ 8 (shop icon 10.4 % defects instead of 0.00 %) | the labels need the smoothed picture; the sub-pixel edges do not suffer from it |

### 8.4 What is new here

To our knowledge the following are not described in the vectorization literature cited above, and are offered as
this project's own contributions (all measured, all reproducible with `bench/`):

1. **A visible-defect metric for vectorization** (§4): CIEDE2000 > 5 after a morphological opening that removes the
   anti-aliasing lines along edges. It exposes merged colors and missing shapes that mean-error scores (and their
   99 %) hide: 1.6 scored 97.99 % on an icon with 18.3 % of it visibly wrong.
2. **An estimation/fitting error decomposition** (§8.1): render the sub-pixel boundary itself as a bound, then
   switch fitting steps off one at a time. It located the real losses in minutes.
3. **Two-color mix assignment with pure-color priority** (§3.2): a pixel that is a palette color keeps it; only
   pixels between colors are anti-aliasing. Without the priority a flat grey between black and white was absorbed.
4. **The bow test** (§8.2): telling a gently curved edge from a straight but noisy one by whether the residual is
   systematic.
5. **Shading-aware ink regions and per-stroke ink colors** (§8.2), on top of the ink unmixing of §3.1.
6. **A calibrated vision-language judge** (§5.4): control pairs with a known answer, repeated runs, agreement with
   the pixel metrics, and the judge's findings fed back as fixes (the flag's stars and motto).

### 8.5 Open, for future work

- The remaining fitting loss on small icons (Ferris 99.45 % vs. a 99.80 % bound) sits in details of 1–4 px (a
  small gap, a 1–2 px line). Three explanations were tested and ruled out (§8.3: the label at the ridge, the
  palette, the majority filter), which leaves the contour stage: chains of features one or two pixels wide. That
  is where the next experiment belongs.
- Gradients in the Logo style are flat by design; a future "flat with gradients" style could use the linear and
  radial fits of the region engine.

## 9. Related work in short

| Approach | Examples | Strength | Weakness for our goal |
|---|---|---|---|
| Binary tracing | Potrace [6] | very clean curves | one color; colors need stacking per layer |
| Region + curve fitting | Ardeco [8], Photo2ClipArt [9], this project | fast, editable | quality limited by segmentation |
| Mesh / diffusion | gradient meshes [10], diffusion curves [11] | smooth shading | not portable SVG |
| Differentiable rendering | DiffVG [2], LIVE [3] | high fidelity | minutes per image, GPU |
| Learned generation | StarVector [4], SuperSVG [5] | semantic, compact | domain-limited, large models, non-deterministic |
| Pixel-art upscaling | Kopf & Lischinski [16] | pixel art | reinterprets the art |
| Perception-driven clip-art fitting | Hoshyari et al. [29], PolyFit [24], Bezigons [22] | boundaries as people expect them | needs a segmentation; learned corner metric |
| Line-drawing vectorization | Favreau et al. [25], Noris et al. [26] | strokes with width, clean topology | line art only |
| Segmentation-driven / hybrid | SRM [31], Xia et al. [32], VTracer [35], SAMVG [33], O&R [34] | statistical merging, patches, fast clustering, learned masks + optimization | deep models (SAM) are heavy; DiffVG steps need a GPU |
| Efficient optimization | Less is More [36] | fewer, adaptively parameterized paths (evaluated with MSE, PSNR, SSIM, LPIPS and path count) | GPU optimization per picture |
| Layered / semantic | semantic simplification [37], LayerTracer [38], OmniSVG [39] | layers that follow the picture's meaning, as designers draw | diffusion / large models; generation more than tracing |
| Robust learned vectorization | VectorArk [40] | rounded-polygon primitives and a degradation model for real-world pictures | a vision-language model |
| SVG evaluation | structural metrics [41], SVGEval [42], StarVector's SVG-Bench [4] | argue that pixel metrics miss what matters in an SVG | aimed at generated SVG; no visible-defect measure for tracing |

## References

1. M. Dziuba, I. Jarsky, V. Efimova, A. Filchenkov. *Image Vectorization: a Review.* arXiv:2306.06441, 2023.
2. T.-M. Li, M. Lukáč, M. Gharbi, J. Ragan-Kelley. *Differentiable Vector Graphics Rasterization for Editing and
   Learning.* ACM Transactions on Graphics 39(6), SIGGRAPH Asia 2020.
3. X. Ma, Y. Zhou, X. Xu, B. Sun, V. Filev, N. Orlov, Y. Fu, H. Shi. *Towards Layer-wise Image Vectorization.*
   CVPR 2022, pp. 16314–16323.
4. J. A. Rodriguez, A. Puri, S. Agarwal, I. H. Laradji, P. Rodriguez, S. Rajeswar, D. Vazquez, C. Pal,
   M. Pedersoli. *StarVector: Generating Scalable Vector Graphics Code from Images and Text.* CVPR 2025
   (arXiv:2312.11556).
5. T. Hu, R. Yi, B. Qian, J. Zhang, P. L. Rosin, Y.-K. Lai. *SuperSVG: Superpixel-based Scalable Vector Graphics
   Synthesis.* CVPR 2024 (arXiv:2406.09794).
6. P. Selinger. *Potrace: a polygon-based tracing algorithm.* 2003. https://potrace.sourceforge.net/potrace.pdf
7. K. He, J. Sun, X. Tang. *Guided Image Filtering.* IEEE TPAMI 35(6), 2013 (ECCV 2010).
8. G. Lecot, B. Lévy. *Ardeco: Automatic Region Detection and Conversion.* Eurographics Symposium on Rendering 2006.
9. J.-D. Favreau, F. Lafarge, A. Bousseau. *Photo2ClipArt: Image Abstraction and Vectorization Using Layered
   Linear Gradients.* ACM Transactions on Graphics 36(6), SIGGRAPH Asia 2017.
10. J. Sun, L. Liang, F. Wen, H.-Y. Shum. *Image Vectorization using Optimized Gradient Meshes.* ACM Transactions on
    Graphics 26(3), SIGGRAPH 2007.
11. A. Orzan, A. Bousseau, H. Winnemöller, P. Barla, J. Thollot, D. Salesin. *Diffusion Curves: A Vector
    Representation for Smooth-Shaded Images.* ACM Transactions on Graphics 27(3), SIGGRAPH 2008.
12. P. J. Schneider. *An Algorithm for Automatically Fitting Digitized Curves.* Graphics Gems, Academic Press, 1990.
13. D. Arthur, S. Vassilvitskii. *k-means++: The Advantages of Careful Seeding.* SODA 2007.
14. D. H. Douglas, T. K. Peucker. *Algorithms for the Reduction of the Number of Points Required to Represent a
    Digitized Line or its Caricature.* Cartographica 10(2), 1973.
15. G. Sharma, W. Wu, E. N. Dalal. *The CIEDE2000 Color-Difference Formula: Implementation Notes, Supplementary Test
    Data, and Mathematical Observations.* Color Research & Application 30(1), 2005.
16. J. Kopf, D. Lischinski. *Depixelizing Pixel Art.* ACM Transactions on Graphics 30(4), SIGGRAPH 2011.
17. X. Wang, L. Xie, C. Dong, Y. Shan. *Real-ESRGAN: Training Real-World Blind Super-Resolution with Pure Synthetic
    Data.* ICCV Workshops 2021.
18. Z. Wang, A. C. Bovik, H. R. Sheikh, E. P. Simoncelli. *Image Quality Assessment: From Error Visibility to
    Structural Similarity.* IEEE Transactions on Image Processing 13(4), 2004.
19. R. Zhang, P. Isola, A. A. Efros, E. Shechtman, O. Wang. *The Unreasonable Effectiveness of Deep Features as a
    Perceptual Metric.* CVPR 2018.
20. T. Y. Zhang, C. Y. Suen. *A Fast Parallel Algorithm for Thinning Digital Patterns.* Communications of the ACM
    27(3), 1984 (center-line style).
21. L. Zheng, W.-L. Chiang, Y. Sheng, S. Zhuang, Z. Wu, Y. Zhuang, Z. Lin, Z. Li, D. Li, E. P. Xing, H. Zhang,
    J. E. Gonzalez, I. Stoica. *Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena.* NeurIPS 2023 Datasets and
    Benchmarks.
22. M. Yang, H. Chao, C. Zhang, J. Guo, L. Yuan, J. Sun. *Effective Clipart Image Vectorization through Direct
    Optimization of Bezigons.* IEEE Transactions on Visualization and Computer Graphics 22(2), 2016
    (arXiv:1602.01913).
23. J. Yang, N. Vining, S. Kheradmand, N. Carr, L. Sigal, A. Sheffer. *Subpixel Deblurring of Anti-Aliased Raster
    Clip-Art.* Computer Graphics Forum 42(2), 2023, pp. 61–76.
24. E. A. Dominici, N. Schertler, J. Griffin, S. Hoshyari, L. Sigal, A. Sheffer. *PolyFit: Perception-Aligned
    Vectorization of Raster Clip-Art via Intermediate Polygonal Fitting.* ACM Transactions on Graphics 39(4),
    SIGGRAPH 2020.
25. J.-D. Favreau, F. Lafarge, A. Bousseau. *Fidelity vs. Simplicity: a Global Approach to Line Drawing
    Vectorization.* ACM Transactions on Graphics 35(4), SIGGRAPH 2016.
26. G. Noris, A. Hornung, R. W. Sumner, M. Simmons, M. Gross. *Topology-Driven Vectorization of Clean Line
    Drawings.* ACM Transactions on Graphics 32(1), 2013.
27. A. W. Fitzgibbon, M. Pilu, R. B. Fisher. *Direct Least Square Fitting of Ellipses.* IEEE Transactions on Pattern
    Analysis and Machine Intelligence 21(5), 1999, pp. 476–480.
28. R. Halíř, J. Flusser. *Numerically Stable Direct Least Squares Fitting of Ellipses.* WSCG 1998.
29. S. Hoshyari, E. A. Dominici, A. Sheffer, N. Carr, Z. Wang, D. Ceylan, I.-C. Shen. *Perception-Driven
    Semi-Structured Boundary Vectorization.* ACM Transactions on Graphics 37(4), SIGGRAPH 2018.
30. M. E. Celebi. *Improving the Performance of K-Means for Color Quantization.* Image and Vision Computing 29(4),
    2011, pp. 260–271.
31. R. Nock, F. Nielsen. *Statistical Region Merging.* IEEE Transactions on Pattern Analysis and Machine
    Intelligence 26(11), 2004, pp. 1452–1458.
32. T. Xia, B. Liao, Y. Yu. *Patch-Based Image Vectorization with Automatic Curvilinear Feature Alignment.* ACM
    Transactions on Graphics 28(5), SIGGRAPH Asia 2009.
33. H. Zhu et al. *SAMVG: A Multi-Stage Image Vectorization Model with the Segment-Anything Model.* ICASSP 2024
    (arXiv:2311.05276).
34. O. Hirschorn, A. Jevnisek, S. Avidan. *Optimize & Reduce: A Top-Down Approach for Image Vectorization.*
    arXiv:2312.11334, 2023.
35. visioncortex. *VTracer.* Open-source raster-to-vector converter, https://github.com/visioncortex/vtracer.
36. Zhao et al. *Less is More: Efficient Image Vectorization with Adaptive Parameterization.* CVPR 2025.
37. Z. Wang et al. *Layered Image Vectorization via Semantic Simplification.* arXiv:2406.05404, 2024.
38. Song, Chen, Shou. *LayerTracer: Cognitive-Aligned Layered SVG Synthesis via Diffusion Transformer.*
    arXiv:2502.01105, 2025.
39. *OmniSVG: A Unified Scalable Vector Graphics Generation Model.* arXiv:2504.06263, 2025 (NeurIPS 2025).
40. T. Gehlaut, D. Liu, C. Bansal, K. Malani, S. Chakraborty, A. Phogat, M. Fisher, V. Batra. *VectorArk: Learning
    Practical Image Vectorization with Rounded Polygon Representation.* CVPR 2026 (arXiv:2605.24398).
41. H. Zhu, A. Deganutti, E. Hirsch, P. Mehta. *Structural Evaluation Metrics for SVG Generation via Leave-One-Out
    Analysis.* arXiv:2604.08809, 2026.
42. *SVGEval: A Vision-Grounded Framework for Perceptual-Quality Benchmarking and Evaluation in Text-to-SVG
    Generation.* arXiv:2608.01977, 2026.
43. F. Wilcoxon. *Individual Comparisons by Ranking Methods.* Biometrics Bulletin 1(6), 1945, pp. 80–83.
44. D. S. Kerby. *The Simple Difference Formula: An Approach to Teaching Nonparametric Correlation.* Comprehensive
    Psychology 3, 2014.
45. B. Efron, R. J. Tibshirani. *An Introduction to the Bootstrap.* Chapman & Hall, 1993.
46. J. Immerkær. *Fast Noise Variance Estimation.* Computer Vision and Image Understanding 64(2), 1996,
    pp. 300–302.
47. D. L. Donoho, I. M. Johnstone. *Ideal Spatial Adaptation by Wavelet Shrinkage.* Biometrika 81(3), 1994,
    pp. 425–455.
48. C. Tomasi, R. Manduchi. *Bilateral Filtering for Gray and Color Images.* ICCV 1998, pp. 839–846.
