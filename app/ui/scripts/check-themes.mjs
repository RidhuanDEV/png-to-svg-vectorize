// WCAG 2.x contrast for every theme (src/theme/themes.json). Text ≥ 4.5:1, UI components and focus/borders of
// controls ≥ 3:1. A failure means a token change broke readability: fix the token, never the threshold.
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const themes = JSON.parse(readFileSync(new URL('../src/theme/themes.json', import.meta.url), 'utf8'));

function rgb(hex) {
  const m = /^#([0-9a-f]{6})$/i.exec(hex);
  if (!m) throw new Error(`not a #rrggbb color: ${hex}`);
  return [0, 2, 4].map((i) => parseInt(m[1].slice(i, i + 2), 16) / 255);
}
const lum = (hex) => {
  const [r, g, b] = rgb(hex).map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};
export const contrast = (a, b) => {
  const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p);
  return (x + 0.05) / (y + 0.05);
};

// [foreground, background, minimum]
const PAIRS = [
  ['text', 'bg', 4.5],
  ['text', 'panel', 4.5],
  ['text', 'panel-2', 4.5],
  ['text', 'panel-3', 4.5],
  ['text', 'accent-soft', 4.5],
  ['text', 'seg-on', 4.5],
  ['muted', 'bg', 4.5],
  ['muted', 'panel', 4.5],
  ['muted', 'panel-2', 4.5],
  ['accent-text', 'accent', 4.5],
  ['accent', 'panel', 3],
  ['accent', 'bg', 3],
  ['node', 'panel', 3],
  ['line-strong', 'panel', 3],
  ['danger', 'panel', 4.5],
  ['danger', 'danger-soft', 4.5],
  ['ok', 'panel', 4.5],
  ['ok', 'ok-soft', 4.5],
  ['warn', 'panel', 4.5],
];

const REQUIRED = new Set(PAIRS.flatMap(([a, b]) => [a, b]));
let failed = 0;
for (const [name, theme] of Object.entries(themes)) {
  for (const key of REQUIRED) if (!(key in theme.tokens)) {
    console.error(`${name}: missing token ${key}`);
    failed++;
  }
  for (const [fg, bg, min] of PAIRS) {
    const ratio = contrast(theme.tokens[fg], theme.tokens[bg]);
    if (ratio < min) {
      console.error(`${name}: ${fg} on ${bg} = ${ratio.toFixed(2)}:1 (needs ${min}:1)`);
      failed++;
    }
  }
}
const names = Object.keys(themes);
const keys = names.map((n) => Object.keys(themes[n].tokens).sort().join(','));
if (new Set(keys).size !== 1) {
  console.error('themes do not define the same tokens');
  failed++;
}
// components must use the theme tokens: a literal color would not follow the theme
const src = fileURLToPath(new URL('../src/', import.meta.url));
const walk = (dir) => readdirSync(dir).flatMap((f) => (statSync(join(dir, f)).isDirectory() ? walk(join(dir, f)) : [join(dir, f)]));
for (const file of walk(src).filter((f) => /\.(svelte|css)$/.test(f))) {
  const text = readFileSync(file, 'utf8').replace(/<!--[\s\S]*?-->/g, '');
  const hit = /(?<![\w&{])#[0-9a-fA-F]{3,8}\b(?!\s*=)/.exec(text.replace(/\{#\w+/g, '').replace(/href="[^"]*"/g, ''));
  if (hit) fail2(`${file}: literal color ${hit[0]} — use a theme token`);
}
function fail2(msg) {
  console.error(msg);
  failed++;
}
if (failed) process.exit(1);
console.log(`themes ok: ${names.join(', ')} (${PAIRS.length} pairs each)`);
