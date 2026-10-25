// Client for the local service. Every /api call carries the per-session token, which arrives once in the URL
// fragment (#t=...) - fragments are never sent to the server or written to its logs.

export type Status = 'staged' | 'queued' | 'running' | 'done' | 'error' | 'cancelled';

export interface Job {
  id: string;
  name: string;
  preset: string;
  options: Partial<Overrides>;
  status: Status;
  stage: string;
  progress: number;
  /** 1-based place in the queue while waiting. */
  position: number | null;
  width: number;
  height: number;
  seconds: number | null;
  source_bytes: number;
  /** Name the result is saved under (Settings → file name pattern). */
  filename: string;
  bytes: number | null;
  /** `palette`: the colors used, largest area first (palette and black & white modes only). */
  stats: { regions?: number; gradients?: number; outline_paths?: number; ai?: boolean; palette?: string[] };
  error: string | null;
}

export interface Overrides {
  outlines: boolean;
  gradients: boolean;
  radial: boolean;
  tolerance: number;
  smooth: number;
  merge_de: number;
  scale: number | null;
  decimals: number;
  ai: AiModelName;
  ai_auto: boolean;
  speckle: number;
  seam: number;
  /** at most this many flat colors (null = free colors and gradients) */
  max_colors: number | null;
  /** fixed colors '#RRGGBB'; every fill and the ink take the nearest one */
  palette: string[];
  color_mode: ColorMode;
  threshold: number;
  remove_bg: boolean;
  layout: Layout;
}

export type ColorMode = 'color' | 'grayscale' | 'bw';
export type Layout = 'stacked' | 'cutout';
export type ExportFormat = 'svg' | 'pdf' | 'eps' | 'dxf';

/** A validated style profile (see /api/profiles/check). */
export interface StyleProfile {
  name: string;
  preset: string;
  options: Partial<Overrides>;
}

export type AiModelName = 'illustration' | 'general';
export type AiAccel = 'auto' | 'gpu' | 'cpu';

export interface AiModel {
  name: AiModelName;
  bytes: number;
  source: string;
  state: 'missing' | 'downloading' | 'installed' | 'error';
  progress: number;
  error: 'network' | 'checksum' | null;
}

export interface AiStatus {
  runtime: boolean;
  gpu: string[];
  accel: AiAccel;
  models: AiModel[];
}

export interface OptionSpec {
  name: keyof Overrides;
  type: 'bool' | 'float' | 'int';
  min?: number;
  max?: number;
  step?: number;
}

export interface Preset {
  name: string;
  description: string;
  /** what the preset sets (decimals, AI and the palette are not part of a preset) */
  defaults: Partial<Overrides>;
}

export interface PresetInfo {
  presets: Preset[];
  options: OptionSpec[];
  limits: { max_upload: number; max_side: number; formats: string[] };
}

export type Speed = 'auto' | 'saver' | 'balanced' | 'fast';

export interface ServiceSettings {
  speed: Speed;
  /** The speed "auto" resolved to on this machine. */
  effective: Exclude<Speed, 'auto'>;
  /** What "auto" picks on this machine, whatever is selected now. */
  auto: Exclude<Speed, 'auto'>;
  concurrency: number;
  cpus: number;
  ram_gb: number | null;
  speeds: Record<Exclude<Speed, 'auto'>, number>;
  max_staged: number;
  max_side: number;
  name_pattern: string;
  size_attrs: boolean;
}

export interface ServicePrefs {
  speed?: Speed;
  name_pattern?: string;
  size_attrs?: boolean;
  max_side?: number;
  max_staged?: number;
  ai_accel?: AiAccel;
}

export interface UpdateInfo {
  current: string;
  latest: string | null;
  newer: boolean;
  url: string | null;
}

const TOKEN_KEY = 'pngsvg.token';

function readToken(): string {
  const m = /[#&]t=([^&]+)/.exec(location.hash);
  if (m) {
    const t = decodeURIComponent(m[1]);
    try {
      sessionStorage.setItem(TOKEN_KEY, t);
    } catch {
      /* storage unavailable: keep it in memory only */
    }
    history.replaceState(null, '', location.pathname + location.search);
    return t;
  }
  try {
    return sessionStorage.getItem(TOKEN_KEY) ?? '';
  } catch {
    return '';
  }
}

const token = readToken();

// a session link pasted into an already open tab only changes the fragment: reload to pick the token up
window.addEventListener('hashchange', () => {
  if (/[#&]t=/.test(location.hash)) location.reload();
});

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function call(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  headers.set('X-Token', token);
  const res = await fetch(path, { ...init, headers });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (typeof body?.detail === 'string') detail = body.detail;
    } catch {
      /* not JSON */
    }
    throw new ApiError(res.status, detail);
  }
  return res;
}

function query(params: Record<string, string | undefined>): string {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined) q.set(k, v);
  return q.toString();
}

export const hasToken = () => token.length > 0;

export const api = {
  presets: async (): Promise<PresetInfo> => (await call('/api/presets')).json(),
  jobs: async (): Promise<Job[]> => (await (await call('/api/jobs')).json()).jobs,
  /** Put an image on the workbench (validated, not processed until `start`). */
  stage: async (file: Blob, name: string): Promise<Job> =>
    (
      await call(`/api/jobs?${query({ name, start: 'false' })}`, {
        method: 'POST',
        body: file,
        headers: { 'Content-Type': file.type || 'application/octet-stream' },
      })
    ).json(),
  start: async (ids: string[], preset: string, options: Partial<Overrides>): Promise<Job[]> =>
    (
      await (
        await call('/api/jobs/start', {
          method: 'POST',
          body: JSON.stringify({ ids, preset, options }),
          headers: { 'Content-Type': 'application/json' },
        })
      ).json()
    ).jobs,
  cancelAll: async (): Promise<string[]> => (await (await call('/api/queue/cancel', { method: 'POST' })).json()).cancelled,
  settings: async (): Promise<ServiceSettings> => (await call('/api/settings')).json(),
  putSettings: async (body: ServicePrefs): Promise<ServiceSettings> =>
    (
      await call('/api/settings', {
        method: 'PUT',
        body: JSON.stringify(body),
        headers: { 'Content-Type': 'application/json' },
      })
    ).json(),
  health: async (): Promise<{ version: string }> => (await call('/api/health')).json(),
  ai: async (): Promise<AiStatus> => (await call('/api/ai')).json(),
  aiDownload: async (name: AiModelName): Promise<void> => {
    await call(`/api/ai/models/${name}`, { method: 'POST' });
  },
  aiCancel: async (name: AiModelName): Promise<void> => {
    await call(`/api/ai/models/${name}/cancel`, { method: 'POST' });
  },
  aiRemove: async (name: AiModelName): Promise<void> => {
    await call(`/api/ai/models/${name}`, { method: 'DELETE' });
  },
  checkUpdate: async (): Promise<UpdateInfo> => (await call('/api/update')).json(),
  /** The SVG as saved (with width/height when Settings ask for it). */
  svgDownload: async (id: string): Promise<Blob> => (await call(`/api/jobs/${id}/svg?download=true`)).blob(),
  retry: async (id: string, preset: string, options: Partial<Overrides>): Promise<Job> =>
    (await call(`/api/jobs/${id}/retry?${query({ preset, options: JSON.stringify(options) })}`, { method: 'POST' })).json(),
  cancel: async (id: string): Promise<void> => {
    await call(`/api/jobs/${id}/cancel`, { method: 'POST' });
  },
  remove: async (id: string): Promise<void> => {
    await call(`/api/jobs/${id}`, { method: 'DELETE' });
  },
  svgText: async (id: string): Promise<string> => (await call(`/api/jobs/${id}/svg`)).text(),
  source: async (id: string): Promise<Blob> => (await call(`/api/jobs/${id}/source`)).blob(),
  zip: async (ids: string[], format: ExportFormat = 'svg'): Promise<Blob> =>
    (await call(`/api/export.zip?${query({ ids: ids.join(','), format })}`)).blob(),
  exportFile: async (id: string, format: ExportFormat): Promise<Blob> =>
    (await call(`/api/jobs/${id}/export?${query({ format })}`)).blob(),
  checkProfile: async (text: string): Promise<StyleProfile> =>
    (await call('/api/profiles/check', { method: 'POST', body: text, headers: { 'Content-Type': 'application/json' } })).json(),
};
