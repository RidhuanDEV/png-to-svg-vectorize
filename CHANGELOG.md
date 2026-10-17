# Changelog

All notable changes. Benchmarks for every engine version are in [docs/bench.md](docs/bench.md).

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
