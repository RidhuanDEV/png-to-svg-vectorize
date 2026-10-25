// Style profiles: a style plus fine-tune choices under a name, kept in this browser and shareable as
// `<name>.pngsvg-profile.json` (the same file the command line reads with --profile).

import { api, type Overrides, type StyleProfile } from './api';
import { saveProfileFile } from './platform';
import { saveSettings, store } from './store.svelte';

const KEY = 'pngsvg.profiles.v1';
/** AI is a per-computer choice (Settings), not part of a shared style. */
const NOT_IN_PROFILE: (keyof Overrides)[] = ['ai', 'ai_auto'];

function load(): StyleProfile[] {
  try {
    const list: unknown = JSON.parse(localStorage.getItem(KEY) ?? '[]');
    if (!Array.isArray(list)) return [];
    return list.filter(
      (p): p is StyleProfile =>
        !!p && typeof p.name === 'string' && typeof p.preset === 'string' && typeof p.options === 'object' && p.options !== null,
    );
  } catch {
    return [];
  }
}

export const profiles = $state({ list: load() });

function persist(): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(profiles.list));
  } catch {
    /* ignore: profiles then last for this session */
  }
}

function currentOptions(): Partial<Overrides> {
  const o: Partial<Overrides> = { ...store.settings.overrides };
  for (const k of NOT_IN_PROFILE) delete o[k];
  return o;
}

/** File content in the shared format. */
export function profileText(name: string): string {
  return JSON.stringify({ format: 'pngsvg-profile', version: 1, name, preset: store.settings.preset, options: currentOptions() }, null, 2) + '\n';
}

/** Save the current style under a name (replaces a profile with the same name). */
export function saveCurrent(name: string): void {
  const p: StyleProfile = { name, preset: store.settings.preset, options: currentOptions() };
  profiles.list = [...profiles.list.filter((x) => x.name !== name), p].sort((a, b) => a.name.localeCompare(b.name));
  persist();
}

export function removeProfile(name: string): void {
  profiles.list = profiles.list.filter((p) => p.name !== name);
  persist();
}

export function applyProfile(p: StyleProfile): void {
  store.settings.preset = p.preset;
  store.settings.overrides = { ...p.options };
  saveSettings();
}

/** Import a profile file: validated by the service (same rules as the command line), then saved and applied. */
export async function importProfile(file: File): Promise<StyleProfile> {
  if (file.size > 64 * 1024) throw new Error('too large');
  const p = await api.checkProfile(await file.text());
  const named: StyleProfile = { ...p, name: p.name || file.name.replace(/\.pngsvg-profile\.json$|\.json$/i, '') };
  profiles.list = [...profiles.list.filter((x) => x.name !== named.name), named].sort((a, b) => a.name.localeCompare(b.name));
  persist();
  applyProfile(named);
  return named;
}

export function exportProfile(name: string): Promise<boolean> {
  return saveProfileFile(name, profileText(name));
}
