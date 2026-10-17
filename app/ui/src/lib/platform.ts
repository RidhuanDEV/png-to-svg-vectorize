// Web mode saves through browser downloads; the desktop app (pywebview) exposes native dialogs via
// window.pywebview.api. File paths never travel over HTTP: Python reads/writes them itself.

import { api } from './api';

export interface FileError {
  name: string;
  code: number;
  detail: string;
}

export interface DesktopPrefs {
  save_dir: string | null;
  ask_each_time: boolean;
  log: boolean;
  log_dir: string;
}

interface DesktopApi {
  open_files(): Promise<{ ids: string[]; errors: FileError[] }>;
  set_close_message(template: string): Promise<void>;
  get_prefs(): Promise<DesktopPrefs>;
  set_pref(key: 'ask_each_time' | 'log', value: boolean): Promise<DesktopPrefs>;
  choose_save_dir(): Promise<DesktopPrefs>;
  clear_save_dir(): Promise<DesktopPrefs>;
  open_log_folder(): Promise<boolean>;
  open_url(url: string): Promise<boolean>;
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


/** Desktop: native multi-file dialog; the photos go on the workbench (not processed yet). Returns the new
 * job ids and per-file errors. Web: null (the page uses an <input type=file>). */
export async function openNative(): Promise<{ ids: string[]; errors: FileError[] } | null> {
  return isDesktop() ? window.pywebview!.api.open_files() : null;
}

/** Native messages (the close confirmation) follow the page language: the page sends the translated text. */
export function setCloseMessage(template: string): void {
  if (isDesktop() && typeof window.pywebview!.api.set_close_message === 'function')
    void window.pywebview!.api.set_close_message(template);
}

/** Desktop-only preferences (save folder, log); null in web mode. */
export const desktop = (): DesktopApi | null => (isDesktop() ? window.pywebview!.api : null);

/** External links: the desktop app opens the project's pages in the system browser; web mode uses a new tab. */
export function openExternal(url: string): void {
  if (isDesktop()) void window.pywebview!.api.open_url(url);
  else window.open(url, '_blank', 'noopener,noreferrer');
}

/** Returns false when the user cancelled the desktop save dialog. Web mode downloads the SVG as the service
 * saves it (Settings → file name, width/height). */
export async function saveSvg(id: string, filename: string): Promise<boolean> {
  if (isDesktop()) return window.pywebview!.api.save_svg(id);
  download(await api.svgDownload(id), filename);
  return true;
}

/** Returns how many files were written (desktop; 0 = cancelled) or the number zipped (web). */
export async function saveAll(ids: string[]): Promise<number> {
  if (isDesktop()) return window.pywebview!.api.save_all(ids);
  download(await api.zip(ids), 'png2svg-results.zip');
  return ids.length;
}
