# Comparing with other vectorizers (manual)

Paid tools (Vectorizer.ai, Adobe Illustrator Image Trace, …) cannot be run in CI, and their outputs must not be
redistributed here without permission. This page is a template for a fair, repeatable manual comparison; fill it in
and keep the numbers, not the third-party files.

## Method

1. Download the comparison set: `python bench/fetch_sets.py` (CC0 / public-domain images, see
   [bench/sets/SOURCES.md](../bench/sets/SOURCES.md)).
2. Pick 5–8 images that cover the categories (e.g. `cute-girl`, `astronaut`, `penguin`, `mountain-landscape`,
   `flag-brazil`, `icon-shop`, `great-wave`).
3. Vectorize each with the other tool using its **default** settings for that kind of image, export SVG, and save it
   locally as `out/compare/<tool>/<image>.svg` (`out/` is not committed).
4. Measure every SVG the same way:

   ```bash
   python - <<'EOF'
   import sys, pathlib
   sys.path.insert(0, 'src'); sys.path.insert(0, 'bench')
   from PIL import Image
   from pngsvg.core import flatten
   from pngsvg.compare import render, similarity
   from run import count_segments
   for svg in sorted(pathlib.Path('out/compare').glob('*/*.svg')):
       img = flatten(Image.open(f'bench/sets/images/{svg.stem}.png'))
       text = svg.read_text(encoding='utf-8')
       sim, within = similarity(img, render(text, *img.size))
       print(f'{svg.parent.name:14s} {svg.stem:20s} {sim:6.2f} % {len(text.encode()) // 1024:6d} KB {count_segments(text):7d} seg')
   EOF
   ```

5. Compare at 200 % zoom with the checklist in [PLAN.md §8](PLAN.md): jagged lines, gaps, gradient bands,
   mouths/eyes, blush, light rims, hairlines. Note what each tool does better.

## Results

Date: ____ · Tool versions: ____ · PNG to SVG Vectorize version: ____

| Image | Tool | Similarity | Size | Segments | Pure paths? | Notes (2× zoom) |
|---|---|---|---|---|---|---|
| cute-girl | PNG to SVG Vectorize |  |  |  | yes |  |
| cute-girl | Vectorizer.ai |  |  |  |  |  |
| cute-girl | Illustrator Image Trace |  |  |  |  |  |
|  |  |  |  |  |  |  |

*Pure paths?* = only `path`/`rect`/`g`/gradients, no embedded raster, filters or scripts (matters for apps such as
Flutter, Figma and Android vector drawables).
