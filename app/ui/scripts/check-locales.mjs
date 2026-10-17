// Every language file in src/locales has exactly the keys of en.json, non-empty texts and the same {placeholders}.
import { readdirSync, readFileSync } from 'node:fs';

const dir = new URL('../src/locales/', import.meta.url);
const load = (f) => JSON.parse(readFileSync(new URL(f, dir), 'utf8'));
const en = load('en.json');
// texts that show placeholder syntax to the user instead of filling it in (translated on purpose)
const LITERAL = new Set(['namePatternHint']);
const ph = (s) => [...s.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort().join(',');

let failed = 0;
const fail = (msg) => {
  console.error(msg);
  failed++;
};
const files = readdirSync(dir).filter((f) => f.endsWith('.json'));
for (const f of files) {
  const d = load(f);
  for (const k of Object.keys(en)) {
    if (!(k in d)) fail(`${f}: missing "${k}"`);
    else if (typeof d[k] !== 'string' || !d[k].trim()) fail(`${f}: "${k}" is empty`);
    else if (!LITERAL.has(k) && ph(d[k]) !== ph(en[k])) fail(`${f}: "${k}" placeholders {${ph(d[k])}} ≠ {${ph(en[k])}}`);
  }
  for (const k of Object.keys(d)) if (!(k in en)) fail(`${f}: unknown key "${k}"`);
}
if (failed) process.exit(1);
console.log(`locales ok: ${files.join(', ')} (${Object.keys(en).length} keys)`);
