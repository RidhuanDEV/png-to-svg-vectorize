// After `next build` (static export): Next 16 writes segment prefetch payloads as folders
// (`__next.$d$lang/__PAGE__.txt`) while the client router requests them as flat names
// (`__next.$d$lang.__PAGE__.txt`). On a static host such as GitHub Pages that is a 404 for every prefetch, so each
// payload is also copied to its flat name. Idempotent.

import { copyFileSync, readdirSync, statSync } from "node:fs";
import { dirname, join, relative, sep } from "node:path";
import { fileURLToPath } from "node:url";

const out = join(dirname(fileURLToPath(import.meta.url)), "..", "out");
let copied = 0;

function files(dir) {
  return readdirSync(dir).flatMap((f) => {
    const p = join(dir, f);
    return statSync(p).isDirectory() ? files(p) : [p];
  });
}

function walk(dir) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (!statSync(p).isDirectory()) continue;
    if (name.startsWith("__next.")) {
      for (const f of files(p)) {
        copyFileSync(f, join(dir, `${name}.${relative(p, f).split(sep).join(".")}`));
        copied++;
      }
    } else {
      walk(p);
    }
  }
}

walk(out);
console.log(`flatten-segments: ${copied} prefetch payloads`);
