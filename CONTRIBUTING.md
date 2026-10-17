# Contributing

Thank you for helping! Everything here is free and open source (MIT).

## Translate the app

The interface texts live in `app/ui/src/locales/<language-code>.json` (for example `en.json`, `id.json`).

1. Copy `en.json` to `<code>.json` (use a short language code such as `de`, `ja`, `pt-br`).
2. Set `"_name"` to the language's own name (for example `"Deutsch"`), then translate every value. Keep the keys and
   the `{placeholders}` (`{n}`, `{name}`, ...) exactly as they are.
3. Run `npm run check` in `app/ui`: it fails if a key is missing or a placeholder differs.

The new language appears in the language list automatically.

Write for people who are not technical: say what happens and what to do next, in short sentences.

## Develop

```bash
pip install -e ".[dev,app]"
cd app/ui && npm ci && npm run build && cd ../..
pytest -q                                   # engine + service
cd app/ui && npm run check && npm run e2e   # UI: types, theme contrast, locales, end-to-end
```

Themes are defined in `app/ui/src/theme/themes.json`; components only use the tokens (CSS variables), never literal
colors — `npm run check` enforces it together with WCAG contrast.

Quality changes to the engine must not make `bench/` worse: run `python bench/run.py --baseline bench/baseline.json`.

## Report a problem

Open an issue with the app version (Settings → About), your system, and — if you can share it — the picture.
