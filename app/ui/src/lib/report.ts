// Batch report (CSV or JSON) of finished results: file, style, size, time, colors and the similarity score, which is
// measured in the page for results that were not opened yet.

import type { Job } from './api';

export interface ReportRow {
  file: string;
  saved_as: string;
  style: string;
  width: number;
  height: number;
  similarity: number | null;
  svg_bytes: number | null;
  seconds: number | null;
  regions: number | null;
  gradients: number | null;
  outline_paths: number | null;
  colors: string;
  ai: boolean;
  options: string;
}

export function reportRow(job: Job, score: number | undefined): ReportRow {
  return {
    file: job.name,
    saved_as: job.filename,
    style: job.preset,
    width: job.width,
    height: job.height,
    similarity: score === undefined ? null : Math.round(score * 100) / 100,
    svg_bytes: job.bytes,
    seconds: job.seconds,
    regions: job.stats.regions ?? null,
    gradients: job.stats.gradients ?? null,
    outline_paths: job.stats.outline_paths ?? null,
    colors: (job.stats.palette ?? []).join(' '),
    ai: !!job.stats.ai,
    options: JSON.stringify(job.options),
  };
}

/** A CSV cell: quoted when needed; text that a spreadsheet would run as a formula gets a leading apostrophe. */
function cell(v: string | number | boolean | null): string {
  if (v === null) return '';
  let s = String(v);
  if (typeof v === 'string' && /^[=+\-@\t\r]/.test(s)) s = "'" + s;
  return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

export function toCsv(rows: ReportRow[]): string {
  const cols: (keyof ReportRow)[] = [
    'file',
    'saved_as',
    'style',
    'width',
    'height',
    'similarity',
    'svg_bytes',
    'seconds',
    'regions',
    'gradients',
    'outline_paths',
    'colors',
    'ai',
    'options',
  ];
  return [cols.join(','), ...rows.map((r) => cols.map((c) => cell(r[c])).join(','))].join('\r\n') + '\r\n';
}

export function toJson(rows: ReportRow[]): string {
  return JSON.stringify({ generator: 'png-to-svg-vectorize', created: new Date().toISOString(), results: rows }, null, 2) + '\n';
}
