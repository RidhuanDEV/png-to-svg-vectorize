// Light editing of a result (F8): pick a shape in the SVG, recolor it, give it another shape's color (merge), or
// delete it; undo / redo. The SVG is edited as XML in the page (never inserted into the page as markup) and saved to
// the service, which validates it against the engine's own subset before it replaces the result.

import { api, type Job } from './api';
import { report, setResultSvg, store } from './store.svelte';

export type LayerView = 'all' | 'fill' | 'outline';

const stacks: Record<string, { undo: string[]; redo: string[] }> = $state({});

export const canUndo = (id: string): boolean => (stacks[id]?.undo.length ?? 0) > 0;
export const canRedo = (id: string): boolean => (stacks[id]?.redo.length ?? 0) > 0;

function parse(text: string): Document {
  return new DOMParser().parseFromString(text, 'image/svg+xml');
}

function inherited(el: Element, attr: string): string | null {
  return el.closest(`[${attr}]`)?.getAttribute(attr) ?? null;
}

function paths(doc: Document): Element[] {
  return Array.from(doc.querySelectorAll('path'));
}

let ctx: CanvasRenderingContext2D | null = null;
function context(): CanvasRenderingContext2D | null {
  ctx ??= document.createElement('canvas').getContext('2d');
  return ctx;
}

/** Index of the topmost visible shape under (x, y) in SVG units, or null. */
export function hitTest(text: string, x: number, y: number, layer: LayerView): number | null {
  const c = context();
  if (!c) return null;
  const list = paths(parse(text));
  for (let i = list.length - 1; i >= 0; i--) {
    const el = list[i];
    const inOutline = !!el.closest('#outline');
    if ((layer === 'fill' && inOutline) || (layer === 'outline' && !inOutline)) continue;
    const d = el.getAttribute('d');
    if (!d) continue;
    const p = new Path2D(d);
    if (inherited(el, 'fill') === 'none') {
      c.lineWidth = Math.max(3, Number(inherited(el, 'stroke-width') ?? 1));
      if (c.isPointInStroke(p, x, y)) return i;
    } else if (c.isPointInPath(p, x, y, el.getAttribute('fill-rule') === 'evenodd' ? 'evenodd' : 'nonzero')) {
      return i;
    }
  }
  return null;
}

/** Outline (path data) and current color of shape `i`. Gradient fills report their middle color. */
export function shapeInfo(text: string, i: number): { d: string; color: string } | null {
  const doc = parse(text);
  const el = paths(doc)[i];
  if (!el) return null;
  let paint = inherited(el, 'fill') ?? '#000000';
  if (paint === 'none') paint = inherited(el, 'stroke') ?? '#000000';
  const ref = /^url\(#([^)]+)\)$/.exec(paint);
  if (ref) {
    const stops = Array.from(doc.getElementById(ref[1])?.querySelectorAll('stop') ?? []);
    paint = stops[Math.floor(stops.length / 2)]?.getAttribute('stop-color') ?? '#000000';
  }
  return { d: el.getAttribute('d') ?? '', color: paint.toUpperCase() };
}

export function viewBox(text: string): [number, number] {
  const m = /viewBox="0 0 ([\d.]+) ([\d.]+)"/.exec(text);
  return m ? [Number(m[1]), Number(m[2])] : [1, 1];
}

async function save(job: Job, next: string): Promise<void> {
  const updated = await api.putSvg(job.id, next);
  store.jobs = store.jobs.map((j) => (j.id === updated.id ? updated : j));
  await setResultSvg(updated, await api.svgText(job.id));
}

async function edit(job: Job, change: (el: Element) => void, i: number): Promise<boolean> {
  const before = store.media[job.id]?.svgText;
  if (!before) return false;
  const doc = parse(before);
  const el = paths(doc)[i];
  if (!el) return false;
  change(el);
  try {
    await save(job, new XMLSerializer().serializeToString(doc));
  } catch (e) {
    report(e, job.name);
    return false;
  }
  const s = (stacks[job.id] ??= { undo: [], redo: [] });
  s.undo = [...s.undo.slice(-49), before];
  s.redo = [];
  return true;
}

/** Recolor shape `i` (a gradient becomes a flat color; the gap-filler stroke follows the fill). */
export function recolor(job: Job, i: number, color: string): Promise<boolean> {
  return edit(
    job,
    (el) => {
      if (inherited(el, 'fill') === 'none') {
        el.setAttribute('stroke', color);
        return;
      }
      el.setAttribute('fill', color);
      if (el.hasAttribute('stroke')) el.setAttribute('stroke', color);
    },
    i,
  );
}

export function removeShape(job: Job, i: number): Promise<boolean> {
  return edit(job, (el) => el.remove(), i);
}

async function step(job: Job, from: 'undo' | 'redo'): Promise<void> {
  const s = stacks[job.id];
  const current = store.media[job.id]?.svgText;
  const target = s?.[from].at(-1);
  if (!s || !current || target === undefined) return;
  try {
    await save(job, target);
  } catch (e) {
    report(e, job.name);
    return;
  }
  s[from] = s[from].slice(0, -1);
  const other = from === 'undo' ? 'redo' : 'undo';
  s[other] = [...s[other], current];
}

export const undoEdit = (job: Job): Promise<void> => step(job, 'undo');
export const redoEdit = (job: Job): Promise<void> => step(job, 'redo');
