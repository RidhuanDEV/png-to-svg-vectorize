// Web mode saves through browser downloads; the desktop app (pywebview) exposes native dialogs via
// window.pywebview.api. File paths never travel over HTTP: Python reads/writes them itself.

import { api } from './api';

export interface FileError {
  name: string;
  code: number;
  detail: string;
}

interface DesktopApi {
  open_files(): Promise<{ ids: string[]; errors: FileError[] }>;
  set_lang(lang: string): Promise<void>;
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

/** Desktop: native multi-file dialog; the photos go on the workbench (not processed yet). Returns the new
 * job ids and per-file errors. Web: null (the page uses an <input type=file>). */
export async function openNative(): Promise<{ ids: string[]; errors: FileError[] } | null> {
  return isDesktop() ? window.pywebview!.api.open_files() : null;
}

/** Native messages (the close confirmation) follow the page language. */
export function tellLanguage(lang: string): void {
  if (isDesktop() && typeof window.pywebview!.api.set_lang === 'function') void window.pywebview!.api.set_lang(lang);
}

/** Returns false when the user cancelled the desktop save dialog. */
export async function saveSvg(id: string, name: string, svg: string): Promise<boolean> {
  if (isDesktop()) return window.pywebview!.api.save_svg(id);
  download(new Blob([svg], { type: 'image/svg+xml' }), svgName(name));
  return true;
}

/** Returns how many files were written (desktop; 0 = cancelled) or the number zipped (web). */
export async function saveAll(ids: string[]): Promise<number> {
  if (isDesktop()) return window.pywebview!.api.save_all(ids);
  download(await api.zip(ids), 'png2svg-results.zip');
  return ids.length;
}
