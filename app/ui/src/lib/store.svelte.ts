// Application state: jobs (polled from the service), the workbench selection, settings, and per-job media.
//
// Flow: photos are added to the workbench (status "staged", nothing processed) → the user ticks the ones to
// process and picks a style → they wait in the service's queue → results are compared and saved.

import { api, ApiError, type AiModelName, type AiStatus, type Job, type Overrides, type PresetInfo, type ServiceSettings, type ServicePrefs, type Speed } from './api';
import { tf, t } from './i18n.svelte';
import type { FileError } from './platform';
import { prefs, servicePrefs } from './prefs.svelte';
import { similarity } from './similarity';
import { toast } from './toast.svelte';

export interface Media {
  sourceUrl?: string;
  svgText?: string;
  svgUrl?: string;
  fillUrl?: string;
  outlineUrl?: string;
  score?: number;
}

interface Settings {
  preset: string;
  overrides: Partial<Overrides>;
  advanced: boolean;
}

const SETTINGS_KEY = 'pngsvg.settings';

function loadSettings(): Settings {
  try {
    const s = JSON.parse(localStorage.getItem(SETTINGS_KEY) ?? 'null');
    if (s && typeof s.preset === 'string') return { preset: s.preset, overrides: s.overrides ?? {}, advanced: !!s.advanced };
  } catch {
    /* ignore */
  }
  return { preset: 'cartoon', overrides: {}, advanced: false };
}

export const store = $state({
  jobs: [] as Job[],
  selected: null as string | null,
  info: null as PresetInfo | null,
  service: null as ServiceSettings | null,
  /** optional AI step: runtime, graphics card, model files */
  ai: null as AiStatus | null,
  settings: loadSettings(),
  media: {} as Record<string, Media>,
  /** Workbench ticks: staged job id → chosen for processing (new photos are ticked). */
  picked: {} as Record<string, boolean>,
  /** Ids hidden while their removal can still be undone. */
  hidden: {} as Record<string, boolean>,
  /** Ids that just finished (drives the one-shot success animation). */
  fresh: {} as Record<string, boolean>,
  /** What the centre shows: the workbench (choose photos) or results (compare & save). */
  focus: 'bench' as 'bench' | 'result',
  busy: false,
  offline: false,
});

export function saveSettings(): void {
  try {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(store.settings));
  } catch {
    /* ignore */
  }
}

export function presetDefaults(name: string): Partial<Overrides> | undefined {
  return store.info?.presets.find((p) => p.name === name)?.defaults;
}

const visible = (j: Job) => !store.hidden[j.id];
export const staged = (): Job[] => store.jobs.filter((j) => j.status === 'staged' && visible(j));
/** Running photos first, then the waiting ones in queue order. */
const queueRank = (j: Job) => (j.status === 'running' ? 0 : 1 + (j.position ?? 0));
export const inQueue = (): Job[] =>
  store.jobs.filter((j) => (j.status === 'queued' || j.status === 'running') && visible(j)).sort((a, b) => queueRank(a) - queueRank(b));
export const finished = (): Job[] =>
  store.jobs.filter((j) => (j.status === 'done' || j.status === 'error' || j.status === 'cancelled') && visible(j)).reverse();
export const pickedIds = (): string[] => staged().filter((j) => store.picked[j.id]).map((j) => j.id);
export const selectedJob = (): Job | undefined => store.jobs.find((j) => j.id === store.selected && visible(j));

/** Turn any failure into a sentence a non-technical person can act on. */
export function explain(e: unknown, name?: string): string {
  if (e instanceof ApiError) {
    if (e.status === 413) return tf('err_tooLarge', { name: name ?? '' });
    if (e.status === 415) return tf('err_notImage', { name: name ?? '' });
    if (e.status === 409 && /workbench/i.test(e.message)) return t('err_full');
    if (e.status === 422 && /model not installed/i.test(e.message)) return t('aiNeedsModel');
    if (e.status === 422 && /AI is not available/i.test(e.message)) return t('aiUnavailable');
    return tf('err_generic', { name: name ? ` (${name})` : '', detail: `${e.status}` });
  }
  if (e instanceof TypeError) return t('err_offline'); // fetch failed: the local service is gone
  return tf('err_generic', { name: name ? ` (${name})` : '', detail: String(e).slice(0, 80) });
}

export function report(e: unknown, name?: string): void {
  toast('error', explain(e, name));
}

export function reportFileErrors(errors: FileError[]): void {
  for (const err of errors) report(new ApiError(err.code, err.detail), err.name);
}

let timer: ReturnType<typeof setTimeout> | undefined;
let wasBusy = false;
let batchDone = 0;

export async function refresh(): Promise<void> {
  const before = new Map(store.jobs.map((j) => [j.id, j.status]));
  try {
    store.jobs = await api.jobs();
    store.offline = false;
  } catch (e) {
    if (!store.offline) report(e);
    store.offline = true;
  }
  for (const j of store.jobs) {
    if (j.status === 'done') {
      void ensureMedia(j);
      if (before.has(j.id) && before.get(j.id) !== 'done') {
        store.fresh[j.id] = true;
        batchDone++;
        setTimeout(() => delete store.fresh[j.id], 1600);
      }
    }
  }
  // the selection follows the work: first finished result once there is one
  if (!selectedJob()) store.selected = finished().find((j) => j.status === 'done')?.id ?? null;
  const busy = store.jobs.some((j) => j.status === 'queued' || j.status === 'running');
  if (wasBusy && !busy && batchDone > 0) {
    toast('success', tf('t_allDone', { n: batchDone }));
    batchDone = 0;
  }
  wasBusy = busy;
  clearTimeout(timer);
  timer = setTimeout(refresh, busy ? 400 : 2000);
}

export async function init(): Promise<void> {
  try {
    // a fresh service (desktop restart) gets the user's saved limits and file-name settings
    [store.info, store.service] = await Promise.all([api.presets(), api.putSettings(servicePrefs())]);
    void refreshAi();
    if (!store.info.presets.some((p) => p.name === store.settings.preset)) store.settings.preset = 'cartoon';
  } catch (e) {
    report(e);
  }
  await refresh();
}

const loading = new Set<string>();

/** Show a (new or edited) SVG for a result: preview URLs per layer, then the similarity score. */
export async function setResultSvg(job: Job, svg: string): Promise<void> {
  const old = store.media[job.id];
  const sourceUrl = old?.sourceUrl ?? URL.createObjectURL(await api.source(job.id));
  for (const u of [old?.svgUrl, old?.fillUrl, old?.outlineUrl]) if (u) URL.revokeObjectURL(u);
  const blob = (text: string) => URL.createObjectURL(new Blob([text], { type: 'image/svg+xml' }));
  const media: Media = {
    sourceUrl,
    svgText: svg,
    svgUrl: blob(svg),
    fillUrl: blob(svg.replace(/<g id="outline"[\s\S]*?<\/g>/, '')),
    outlineUrl: blob(svg.replace('<g id="fill"', '<g id="fill" display="none"')),
  };
  store.media[job.id] = media;
  const score = await similarity(sourceUrl, media.svgUrl!, job.width, job.height, job.stats.crop);
  store.media[job.id] = { ...store.media[job.id], score };
}

/** Load a finished result's preview and score once (also used by the batch report). */
export async function ensureMedia(job: Job): Promise<void> {
  const m = store.media[job.id];
  if ((m && m.svgUrl) || loading.has(job.id)) return;
  loading.add(job.id);
  try {
    await setResultSvg(job, await api.svgText(job.id));
  } catch (e) {
    report(e, job.name);
  } finally {
    loading.delete(job.id);
  }
}

/** Thumbnail for photos that are not finished yet (workbench, queue). */
export async function ensureThumb(job: Job): Promise<void> {
  if (store.media[job.id]?.sourceUrl || loading.has(job.id)) return;
  loading.add(job.id);
  try {
    const src = await api.source(job.id);
    store.media[job.id] = { ...store.media[job.id], sourceUrl: URL.createObjectURL(src) };
  } catch {
    /* the card shows a placeholder */
  } finally {
    loading.delete(job.id);
  }
}

function releaseMedia(id: string): void {
  const m = store.media[id];
  if (!m) return;
  for (const u of [m.sourceUrl, m.svgUrl, m.fillUrl, m.outlineUrl]) if (u) URL.revokeObjectURL(u);
  delete store.media[id];
}

/** Put photos on the workbench. Nothing is processed until `processPicked`. */
export async function addFiles(files: Iterable<File>): Promise<void> {
  let added = 0;
  for (const f of files) {
    try {
      const job = await api.stage(f, f.name);
      store.jobs = [...store.jobs, job];
      store.picked[job.id] = true;
      added++;
    } catch (e) {
      report(e, f.name);
      if (e instanceof ApiError && e.status === 409) break; // workbench full: the rest would fail too
    }
  }
  if (added) {
    store.focus = 'bench';
    toast('info', tf('t_added', { n: added }));
  }
  await refresh();
}

/** Photos the desktop app read through the native dialog (already staged by Python). */
export async function adoptStaged(ids: string[], errors: FileError[]): Promise<void> {
  for (const id of ids) store.picked[id] = true;
  reportFileErrors(errors);
  if (ids.length) {
    store.focus = 'bench';
    toast('info', tf('t_added', { n: ids.length }));
  }
  await refresh();
}

export function pickAll(on: boolean): void {
  for (const j of staged()) store.picked[j.id] = on;
}

export async function processPicked(): Promise<void> {
  const ids = pickedIds();
  if (!ids.length || store.busy) return;
  store.busy = true;
  try {
    const started = await api.start(ids, store.settings.preset, jobOptions());
    for (const j of started) delete store.picked[j.id];
    if (started.length) toast('info', tf('t_queued', { n: started.length }));
    // follow the work: show progress and results; photos left on the workbench stay one click away
    if (started.length) {
      store.focus = 'result';
      store.selected = started[0].id;
    }
  } catch (e) {
    report(e);
  } finally {
    store.busy = false;
  }
  await refresh();
}

/** Style overrides plus the output precision and AI choice from Settings (decimals 1 is the engine default). */
export function jobOptions(): Partial<Overrides> {
  const o: Partial<Overrides> = { ...store.settings.overrides };
  if (prefs.decimals !== 1) o.decimals = prefs.decimals;
  if (aiReady() && prefs.aiMode !== 'off') {
    o.ai = prefs.aiModel;
    if (prefs.aiMode === 'auto') o.ai_auto = true;
  }
  return o;
}

/** The chosen AI model is installed and the runtime works on this computer. */
export const aiReady = (): boolean =>
  !!store.ai?.runtime && store.ai.models.some((m) => m.name === prefs.aiModel && m.state === 'installed');

let aiTimer: ReturnType<typeof setTimeout> | undefined;

export async function refreshAi(): Promise<void> {
  try {
    store.ai = await api.ai();
  } catch {
    store.ai = null; // service without AI support
  }
  clearTimeout(aiTimer);
  if (store.ai?.models.some((m) => m.state === 'downloading')) aiTimer = setTimeout(refreshAi, 400);
}

export async function aiModelAction(action: 'download' | 'cancel' | 'remove', name: AiModelName): Promise<void> {
  try {
    if (action === 'download') await api.aiDownload(name);
    else if (action === 'cancel') await api.aiCancel(name);
    else await api.aiRemove(name);
  } catch (e) {
    report(e);
  }
  await refreshAi();
}

export async function setSpeed(speed: Speed): Promise<void> {
  await updateService({ speed });
}

export async function updateService(body: ServicePrefs): Promise<void> {
  try {
    store.service = await api.putSettings(body);
    await refresh(); // file names shown in the lists follow the pattern
  } catch (e) {
    report(e);
  }
}

export async function cancelJob(id: string): Promise<void> {
  try {
    await api.cancel(id);
  } catch (e) {
    report(e);
  }
  await refresh();
}

export async function stopAll(): Promise<void> {
  try {
    const stopped = await api.cancelAll();
    if (stopped.length) toast('info', tf('t_stopped', { n: stopped.length }));
  } catch (e) {
    report(e);
  }
  await refresh();
}

/** Remove with a few seconds to undo: the photo is hidden at once and deleted on the service afterwards. */
export function removeJob(id: string): void {
  const job = store.jobs.find((j) => j.id === id);
  if (!job) return;
  store.hidden[id] = true;
  if (store.selected === id) store.selected = null;
  let undone = false;
  const ms = 5000;
  toast('info', tf('t_removed', { name: job.name }), {
    ms,
    action: {
      label: t('undo'),
      run: () => {
        undone = true;
        delete store.hidden[id];
      },
    },
  });
  setTimeout(async () => {
    if (undone) return;
    try {
      await api.remove(id);
    } catch (e) {
      if (!(e instanceof ApiError && e.status === 404)) report(e, job.name);
    }
    delete store.hidden[id];
    delete store.picked[id];
    releaseMedia(id);
    await refresh();
  }, ms + 200);
}

export async function retryJob(id: string, useCurrentSettings = false): Promise<void> {
  const job = store.jobs.find((j) => j.id === id);
  if (!job) return;
  try {
    const next = useCurrentSettings
      ? await api.retry(id, store.settings.preset, jobOptions())
      : await api.retry(id, job.preset, job.options);
    await api.remove(id);
    const thumb = store.media[id]?.sourceUrl;
    if (thumb) store.media[next.id] = { sourceUrl: thumb }; // keep the picture while it runs again
    for (const u of [store.media[id]?.svgUrl, store.media[id]?.fillUrl, store.media[id]?.outlineUrl]) if (u) URL.revokeObjectURL(u);
    delete store.media[id];
    store.selected = next.id;
    store.focus = 'result';
  } catch (e) {
    report(e, job.name);
  }
  await refresh();
}
