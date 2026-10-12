// Web mode saves through browser downloads; the desktop app (pywebview) exposes native dialogs via
// window.pywebview.api. File paths never travel over HTTP: Python reads/writes them itself.

import { api } from './api';

interface DesktopApi {
  open_files(): Promise<string[]>;
  save_svg(id: string): Promise<boolean>;
  save_all(ids: string[]): Promise<number>;
}

declare global {
  interface Window {
    pywebview?: { api: DesktopApi };
  }
}

export const isDesktop = (): boolean => typeof window.pywebview?.api?.open_files === 'function';

function download(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}

export function svgName(name: string): string {
  const stem = name.includes('.') ? name.slice(0, name.lastIndexOf('.')) : name;
  return `${stem || 'image'}.svg`;
}

/** Desktop: native multi-file dialog, returns created job ids. Web: null (the page uses an <input type=file>). */
export async function openNative(): Promise<string[] | null> {
  return isDesktop() ? window.pywebview!.api.open_files() : null;
}

export async function saveSvg(id: string, name: string, svg: string): Promise<void> {
  if (isDesktop()) {
    await window.pywebview!.api.save_svg(id);
    return;
  }
  download(new Blob([svg], { type: 'image/svg+xml' }), svgName(name));
}

export async function saveAll(ids: string[]): Promise<void> {
  if (isDesktop()) {
    await window.pywebview!.api.save_all(ids);
    return;
  }
  download(await api.zip(ids), 'png2svg-results.zip');
}
