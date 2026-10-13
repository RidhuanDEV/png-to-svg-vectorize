// One way to add photos from any button: the desktop app's native dialog, else the page's hidden file input.

import { openNative } from './platform';
import { adoptStaged } from './store.svelte';

let fallback: (() => void) | null = null;

/** App registers the hidden <input type=file> once. */
export function registerFileInput(open: () => void): void {
  fallback = open;
}

export async function pickFiles(): Promise<void> {
  const res = await openNative();
  if (res === null) {
    fallback?.();
    return;
  }
  await adoptStaged(res.ids, res.errors);
}
