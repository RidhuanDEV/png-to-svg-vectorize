// Watch folder (desktop app): new pictures in a folder are converted with the current style into another folder.
// The folders are chosen with native dialogs and stay in Python; the page only shows their paths.

import { desktop, type WatchFormat, type WatchStatus } from './platform';
import { jobOptions, store } from './store.svelte';

export const watch = $state({ status: null as WatchStatus | null, error: '' });

let timer: ReturnType<typeof setTimeout> | undefined;

function show(s: WatchStatus): void {
  watch.status = s;
  watch.error = s.error ?? '';
  clearTimeout(timer);
  if (s.watching) timer = setTimeout(() => void refreshWatch(), 2000);
}

export async function refreshWatch(): Promise<void> {
  const d = desktop();
  if (d) show(await d.watch_status());
}

export async function chooseWatchFolder(which: 'source' | 'target'): Promise<void> {
  const d = desktop();
  if (d) show(await d.watch_choose(which));
}

export async function startWatch(format: WatchFormat): Promise<void> {
  const d = desktop();
  if (d) show(await d.watch_start(store.settings.preset, JSON.stringify(jobOptions()), format));
}

export async function stopWatch(): Promise<void> {
  const d = desktop();
  if (d) show(await d.watch_stop());
}
