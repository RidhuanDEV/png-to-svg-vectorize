// Web mode saves through browser downloads; the desktop app (pywebview) exposes native dialogs via
// window.pywebview.api. File paths never travel over HTTP: Python reads/writes them itself.

import { api, type ExportFormat } from './api';

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

export type WatchFormat = 'svg' | 'pdf' | 'eps' | 'dxf';

export interface WatchStatus {
  watching: boolean;
  source: string | null;
  target: string | null;
  format: WatchFormat | null;
  preset: string | null;
  converted: number;
  failed: number;
  waiting: number;
  last_error: string | null;
  error?: string;
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
  save_svg(id: string, fmt: ExportFormat): Promise<boolean>;
  save_all(ids: string[], fmt: ExportFormat): Promise<number>;
  save_png(name: string, dataB64: string): Promise<boolean>;
  save_profile(name: string, text: string): Promise<boolean>;
  save_report(name: string, text: string): Promise<boolean>;
  watch_status(): Promise<WatchStatus>;
  watch_choose(which: 'source' | 'target'): Promise<WatchStatus>;
  watch_start(preset: string, options: string, format: WatchFormat): Promise<WatchStatus>;
  watch_stop(): Promise<WatchStatus>;
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

const withExt = (filename: string, ext: string) => filename.replace(/\.[^.]+$/, '') + '.' + ext;

/** Returns false when the user cancelled the desktop save dialog. Web mode downloads the file as the service
 * saves it (Settings → file name, width/height). */
export async function saveResult(id: string, filename: string, format: ExportFormat = 'svg'): Promise<boolean> {
  if (isDesktop()) return window.pywebview!.api.save_svg(id, format);
  download(format === 'svg' ? await api.svgDownload(id) : await api.exportFile(id, format), withExt(filename, format));
  return true;
}

/** Returns how many files were written (desktop; 0 = cancelled) or the number zipped (web). */
export async function saveAll(ids: string[], format: ExportFormat = 'svg'): Promise<number> {
  if (isDesktop()) return window.pywebview!.api.save_all(ids, format);
  download(await api.zip(ids, format), 'png2svg-results.zip');
  return ids.length;
}

/** Largest canvas browsers render reliably (side and area). */
const MAX_CANVAS_SIDE = 16384;
const MAX_CANVAS_AREA = 120_000_000;

/** The SVG drawn at `scale` × its size (vector-sharp at any scale), as a PNG. Returns the PNG and the scale used,
 * which is lowered when the canvas would be too large. */
export async function renderPng(svgText: string, width: number, height: number, scale: number): Promise<{ png: Blob; scale: number }> {
  const fit = Math.min(scale, MAX_CANVAS_SIDE / Math.max(width, height), Math.sqrt(MAX_CANVAS_AREA / (width * height)));
  const w = Math.max(1, Math.floor(width * fit));
  const h = Math.max(1, Math.floor(height * fit));
  // explicit size, so the image is rasterized at the target resolution
  const sized = svgText.replace(
    /<svg\b([^>]*)>/,
    (_m, attrs: string) => `<svg${attrs.replace(/\s(width|height)="[^"]*"/g, '')} width="${w}" height="${h}">`,
  );
  const url = URL.createObjectURL(new Blob([sized], { type: 'image/svg+xml' }));
  try {
    const img = new Image();
    img.src = url;
    await img.decode();
    const canvas = document.createElement('canvas');
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext('2d');
    if (!ctx) throw new Error('canvas unavailable');
    ctx.drawImage(img, 0, 0, w, h);
    const png = await new Promise<Blob>((resolve, reject) =>
      canvas.toBlob((b) => (b ? resolve(b) : reject(new Error('PNG encoding failed'))), 'image/png'),
    );
    return { png, scale: fit };
  } finally {
    URL.revokeObjectURL(url);
  }
}

async function base64(blob: Blob): Promise<string> {
  const data = await new Promise<string>((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(String(r.result));
    r.onerror = () => reject(r.error ?? new Error('read failed'));
    r.readAsDataURL(blob);
  });
  return data.slice(data.indexOf(',') + 1);
}

export async function savePng(png: Blob, filename: string): Promise<boolean> {
  if (isDesktop()) return window.pywebview!.api.save_png(filename, await base64(png));
  download(png, withExt(filename, 'png'));
  return true;
}

/** Save a batch report (`.csv` or `.json`). */
export async function saveReport(filename: string, text: string): Promise<boolean> {
  if (isDesktop()) return window.pywebview!.api.save_report(filename, text);
  download(new Blob([text], { type: filename.endsWith('.csv') ? 'text/csv' : 'application/json' }), filename);
  return true;
}

/** Save a style profile file (`<name>.pngsvg-profile.json`). */
export async function saveProfileFile(name: string, text: string): Promise<boolean> {
  if (isDesktop()) return window.pywebview!.api.save_profile(name, text);
  download(new Blob([text], { type: 'application/json' }), `${name || 'style'}.pngsvg-profile.json`);
  return true;
}
