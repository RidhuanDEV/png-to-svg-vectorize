// Application state: jobs (polled from the service), selection, settings, and per-job media (blob URLs).

import { api, ApiError, type Job, type Overrides, type PresetInfo } from './api';
import { similarity } from './similarity';

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
  settings: loadSettings(),
  media: {} as Record<string, Media>,
  notice: '',
});

export function saveSettings(): void {
  try {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(store.settings));
  } catch {
    /* ignore */
  }
}

export function presetDefaults(name: string): Overrides | undefined {
  return store.info?.presets.find((p) => p.name === name)?.defaults;
}

export const selectedJob = (): Job | undefined => store.jobs.find((j) => j.id === store.selected);

function report(e: unknown): void {
  store.notice = e instanceof ApiError ? `${e.status}: ${e.message}` : String(e);
  setTimeout(() => (store.notice = ''), 6000);
}

let timer: ReturnType<typeof setTimeout> | undefined;

export async function refresh(): Promise<void> {
  try {
    store.jobs = await api.jobs();
  } catch (e) {
    report(e);
  }
  for (const j of store.jobs) if (j.status === 'done') void ensureMedia(j);
  if (!store.selected && store.jobs.length) store.selected = store.jobs[0].id;
  clearTimeout(timer);
  const busy = store.jobs.some((j) => j.status === 'queued' || j.status === 'running');
  timer = setTimeout(refresh, busy ? 400 : 2000);
}

export async function init(): Promise<void> {
  try {
    store.info = await api.presets();
    if (!store.info.presets.some((p) => p.name === store.settings.preset)) store.settings.preset = 'cartoon';
  } catch (e) {
    report(e);
  }
  await refresh();
}

const loading = new Set<string>();

async function ensureMedia(job: Job): Promise<void> {
  const m = store.media[job.id];
  if ((m && m.svgUrl) || loading.has(job.id)) return;
  loading.add(job.id);
  try {
    const [src, svg] = await Promise.all([api.source(job.id), api.svgText(job.id)]);
    const blob = (text: string) => URL.createObjectURL(new Blob([text], { type: 'image/svg+xml' }));
    const media: Media = {
      sourceUrl: URL.createObjectURL(src),
      svgText: svg,
      svgUrl: blob(svg),
      fillUrl: blob(svg.replace(/<g id="outline"[\s\S]*?<\/g>/, '')),
      outlineUrl: blob(svg.replace('<g id="fill"', '<g id="fill" display="none"')),
    };
    store.media[job.id] = media;
    const score = await similarity(media.sourceUrl!, media.svgUrl!, job.width, job.height);
    store.media[job.id] = { ...store.media[job.id], score };
  } catch (e) {
    report(e);
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

export async function addFiles(files: Iterable<File>): Promise<void> {
  for (const f of files) {
    try {
      const job = await api.upload(f, f.name, store.settings.preset, store.settings.overrides);
      store.jobs = [...store.jobs, job];
      store.selected = job.id;
    } catch (e) {
      report(e instanceof ApiError ? new ApiError(e.status, `${f.name}: ${e.message}`) : e);
    }
  }
  await refresh();
}

export async function adoptJobs(ids: string[]): Promise<void> {
  await refresh();
  if (ids.length) store.selected = ids[ids.length - 1];
}

export async function cancelJob(id: string): Promise<void> {
  try {
    await api.cancel(id);
  } catch (e) {
    report(e);
  }
  await refresh();
}

export async function removeJob(id: string): Promise<void> {
  try {
    await api.remove(id);
  } catch (e) {
    report(e);
  }
  releaseMedia(id);
  if (store.selected === id) store.selected = null;
  await refresh();
}

export async function retryJob(id: string, useCurrentSettings = false): Promise<void> {
  const job = store.jobs.find((j) => j.id === id);
  if (!job) return;
  try {
    const next = useCurrentSettings
      ? await api.retry(id, store.settings.preset, store.settings.overrides)
      : await api.retry(id, job.preset, job.options);
    await api.remove(id);
    releaseMedia(id);
    store.selected = next.id;
  } catch (e) {
    report(e);
  }
  await refresh();
}
