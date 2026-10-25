# Product website

<https://ridhuandev.github.io/png-to-svg-vectorize/> — Next.js (static export) + Tailwind CSS + shadcn/ui, English and
Bahasa Indonesia, published to GitHub Pages by `.github/workflows/site.yml` on every change and every release.

```bash
cd site
npm ci
npm run dev          # http://localhost:3000/png-to-svg-vectorize/
npm run check        # route types + TypeScript + ESLint
npm run build        # static site in out/ (set GITHUB_TOKEN to avoid API rate limits)
```

Content comes from the repository, never copied by hand:

| What | Source | How |
|---|---|---|
| Version, changelog, user guides | `pyproject.toml`, `CHANGELOG.md`, `docs/user-guide.*.md` | `scripts/content.mjs` (every build) |
| Downloads, sizes, SHA-256 | latest GitHub release + its `SHA256SUMS.txt` | `scripts/content.mjs` (CI fails if unavailable) |
| Colors | the app's themes (`app/ui/src/theme/themes.json`): Paper & ink (light), Lightbox (dark) | `scripts/content.mjs` → `src/generated/theme.css` |
| Gallery, numbers, screenshots | `bench/sets` (CC0 / public domain) and `docs/images` | `python site/scripts/assets.py` (output committed) |
| Texts | `src/i18n/en.ts`, `src/i18n/id.ts` (same shape, checked by TypeScript) | — |

Notes:
- `scripts/flatten-segments.mjs` copies Next 16's segment prefetch files to the flat names its client router requests
  (otherwise every prefetch is a 404 on a static host).
- No analytics, cookies, third-party scripts or fonts (IBM Plex is self-hosted through `next/font/local`).
- Next.js 16.4.3 was taken at 2 days old (owner-approved exception to the two-week rule): 16.0–16.4.0 have critical
  advisories and the build refuses to run.
