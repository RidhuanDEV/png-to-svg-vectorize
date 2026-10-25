# Changelog

All notable changes. Benchmarks for every engine version are in [docs/bench.md](docs/bench.md).

## 1.4.0 — 2026-10-25 — studio options

- **Colors**: *Number of colors* (2–32 flat colors, ink included) or a **locked palette**: *Use these colors* on a
  result, then change, add or remove colors (a removed color merges into the nearest); **Grayscale** and
  **Black & white** (with threshold). Results report the colors used (`stats.palette`).
- **Transparent background**: transparent pixels, or else the region covering most of the border, are left out.
  Transparency survives the AI step.
- **Shapes: stacked or cut out** — cut-out shapes keep their holes and never overlap (cutting machines, editing);
  **gap filler** (seam width) and **speck removal** (minimum area) are now fine-tune options.
- **Export formats**: SVG, **PDF** (vector, real gradients), **EPS** (level 3), **DXF** (R12 polylines, one layer per
  color) for the selected result or *Save all*; **PNG** rendered from the vector at 1–8×; **Copy PNG**.
- **Paste** a picture with `Ctrl+V`.
- **Style profiles**: save the current style under a name, pick it again, export/import
  `<name>.pngsvg-profile.json`; the command line reads the same file (`png2svg --profile`).
- CLI: `--format`, `--max-colors`, `--palette`, `--color-mode`, `--threshold`, `--remove-bg`, `--cutout`, `--seam`,
  `--speckle`, `--profile`; `-o out.pdf` picks the format from the extension.
- API: `GET /api/jobs/{id}/export?format=`, `GET /api/export.zip?format=`, `POST /api/profiles/check`; new job
  options `max_colors`, `palette`, `color_mode`, `threshold`, `remove_bg`, `layout`, `seam`, `speckle`.
- Default output is unchanged (byte-identical); Vite 8.3.4 (security fixes in the dev server).

## 1.3.0 — 2026-10-25 — Enhance with AI (optional)

- **Enhance with AI**: before vectorizing, an AI model (Real-ESRGAN, BSD-3-Clause, converted to ONNX) cleans and
  enlarges the photo ×4; the result is traced at 2× the photo size. Biggest effect on small, blurry and JPEG pictures
  (+0.47 similarity points median on damaged copies of E7 images, see [docs/bench.md](docs/bench.md)).
- Off / **Automatic** (default: only photos under 1000 px or JPEGs) / Always — in the style panel. Two models:
  *Illustrations* (default, 17 MB) and *General* (5 MB).
- Models are **not bundled**: Settings → Processing → *Download*, once, from this repository's GitHub release
  `models-v1`, verified by SHA-256 and kept in the user data folder; works offline afterwards. Cancel/remove at any
  time. The ONNX Runtime ships in the installer (DirectML on Windows — any GPU — and CoreML on Apple Silicon, with CPU
  fallback); *Run AI on*: Automatic / Graphics card / Processor only. Not available on macOS Intel (no runtime build).
- API: `GET /api/ai`, `POST`/`DELETE /api/ai/models/{name}`, `POST /api/ai/models/{name}/cancel`; job options
  `ai` (model name) and `ai_auto`; `PUT /api/settings` accepts `ai_accel`; results report `stats.ai`. An AI job whose
  model is missing is refused with 422 instead of silently running without AI.
- Maintainers: `tools/models/convert.py` converts the official weights (loaded with `weights_only=True`) and checks
  the ONNX output against PyTorch; `bench/ai_restore.py` measures the gain. Python extra `[ai]`.

## 1.2.0 — 2026-10-18 — themes and Settings

- **Three themes** to choose from — *Paper & ink*, *Lightbox*, *Blueprint* — or *Match system* (default). Colors live
  in `app/ui/src/theme/themes.json`; `npm run check` verifies WCAG contrast for every theme and that components use
  no literal colors.
- Bundled **IBM Plex Sans / Mono** (SIL OFL); numbers use the monospaced face. Pen-node motif in titles and the new
  brand mark.
- **Settings** (gear or `Ctrl+,`): language, theme, density, text size, reduce animation, guide; processing speed,
  largest photo, workbench size; style for new photos, save folder (desktop), **file name pattern** (`{name}`
  `{style}` `{date}`), **coordinate precision** (engine option `decimals`, 0–3), width/height in the SVG; diagnostic
  log (desktop); version, licenses and a manual **update check** (`GET /api/update`).
- **Languages from files**: `app/ui/src/locales/<code>.json`; a new language is one file (see CONTRIBUTING.md).
- API: `PUT /api/settings` accepts `name_pattern`, `size_attrs`, `max_side`, `max_staged` (each optional); jobs carry
  `filename`; saved/zip/downloaded SVGs follow the pattern and size setting.

## 1.1.0 — 2026-10-13 — friendlier workflow

- **Workbench**: added photos wait (status `staged`) until you press **Process N photos**; tick only the ones you want.
  API: `POST /api/jobs?start=false`, `POST /api/jobs/start` (ids + style), `POST /api/queue/cancel`.
- **Queue that spares the computer**: a real FIFO queue with a limit on simultaneous conversions; **processing speed**
  Automatic (default, from cores and memory) / Saver (1) / Balanced (2) / Fast (≤ 4, one core left free), changeable
  at any time (`GET`/`PUT /api/settings`); workers run at below-normal priority; queue position shown per photo.
- **New interface**: custom components instead of browser/OS controls (buttons, checkbox, switch, segmented control,
  dropdown, slider, progress ring, dialog, toasts with Undo), step indicator, result styles as visual cards,
  micro-interactions (press, hover, drop zone, finish animation) that respect *reduce motion*, plain-language messages
  for every failure, keyboard and screen-reader support.
- **First-run guide** (skippable, Esc; reopen with **Guide**).
- Removing a result can be undone for a few seconds; **Stop all** asks first; closing the desktop window while photos
  are still being converted asks first (in the page language).
- Desktop "Open" now puts photos on the workbench instead of converting them at once.

## 1.0.0 — 2026-10-12

First release of the desktop app for Windows and macOS.

- User guide in English and Bahasa Indonesia ([docs/user-guide.en.md](docs/user-guide.en.md),
  [docs/user-guide.id.md](docs/user-guide.id.md)), screenshots, release notes.
- Comparison set of 27 CC0 / public-domain images (`bench/sets`, downloaded on demand and verified by SHA-256),
  checked in CI together with the synthetic set; template for manual comparisons with other tools.
- Fix: transparent PNGs are flattened onto white instead of black.
- Fix: when the darkest pixels are a colored dark area (a purple flag, deep water) rather than lines, the outline
  color is taken from line pixels.
- `bench/run.py --preset/--only`.
- Fix: `python -m pngsvg` with several files and worker processes failed on Windows/macOS (the worker function
  lived in `__main__`); the CLI now lives in `pngsvg.cli`.

## 0.5.0 — 2026-10-12 — desktop app and installers

- Desktop app (`pngsvg-app`): native window (WebView2 / WKWebView) around the local service, native open / save /
  save-all dialogs (paths never go over HTTP, existing files are never overwritten), settings remembered between runs,
  log file in the user data folder, `--smoke` self-test.
- Packaging: PyInstaller (onedir, no UPX), per-user Inno Setup installer with a WebView2 check, portable zip, DMG for
  Apple Silicon and Intel. `Release` workflow builds and smoke-tests all three, draft release for `v*` tags.
- Builds are not code-signed (see the user guide for the SmartScreen / Gatekeeper steps).

## 0.4.0 — 2026-10-12 — local web UI

- `png2svg serve`: FastAPI service on `127.0.0.1` with a per-session token, Host check, CSP, upload limits (50 MB,
  8000 px), content-based format check, validated options; jobs in a process pool with per-stage progress, cancel,
  re-run, delete, zip export. Results live in memory only.
- UI (Svelte 5): drag and drop, queue, side-by-side and slider comparison with synchronized zoom up to 800 %,
  fills-only / outlines-only views, in-page similarity score, presets and advanced settings, save / save all / copy,
  English and Bahasa Indonesia, light and dark theme.
- Engine: `vectorize(..., on_stage=)` progress callback (output unchanged).

## 0.3.0 — 2026-10-12 — radial gradients, speed, presets

- Elliptical radial gradients for blob shading; concentric bands of a ball or glow are grown back into one region.
- Gradient stops solved by least squares against what a renderer draws.
- Sub-pixel fill boundaries from anti-aliasing and boundary refinement (straight edges, sharp tips).
- Adaptive ink detection for thin outlines; wider anti-aliasing band merging.
- Segmentation about 2× faster; optional process pool (`executor=`, CLI `--jobs`).
- Presets `cartoon`, `flat`, `logo`, `poster` (`--preset`).

## 0.2.0 — 2026-10-12 — shared boundaries and own curve fitting

- Planar map: every boundary between two regions is fitted once and shared (no gaps, no overlap).
- Schneider cubic Bezier fitting with corner detection; looser tolerance for boundaries hidden under outlines.
- vtracer dependency removed. Median file size −58 %, segments −69 % on the reference set.

## 0.1.0 — 2026-10-12 — first version

- Engine `pngsvg`: ink outline separation by color unmixing, gradient-fill regions, pure-path SVG.
- CLI `png2svg`, tests, CI on Windows, macOS and Linux; benchmark scripts and baseline.
