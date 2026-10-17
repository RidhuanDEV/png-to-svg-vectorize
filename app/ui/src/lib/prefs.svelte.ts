// User preferences (Settings): appearance is applied to the page; processing/output limits live on the local service
// and are pushed to it on start, because a desktop restart starts a fresh service.

import themes from '../theme/themes.json';

export type ThemeChoice = 'system' | keyof typeof themes;
export type Density = 'comfortable' | 'compact';
export type Motion = 'system' | 'reduce';

export interface Prefs {
  theme: ThemeChoice;
  density: Density;
  textScale: number;
  motion: Motion;
  /** coordinate decimals of new results (engine option `decimals`) */
  decimals: number;
  /** add width/height to saved SVGs (else viewBox only) */
  sizeAttrs: boolean;
  namePattern: string;
  maxSide: number;
  maxStaged: number;
}

export const THEMES = Object.keys(themes) as (keyof typeof themes)[];
export const TEXT_SCALES = [0.9, 1, 1.15, 1.3];
export const MAX_SIDES = [3000, 4000, 6000, 8000];
export const MAX_STAGED = [25, 50, 100, 200];
const DEFAULTS: Prefs = {
  theme: 'system',
  density: 'comfortable',
  textScale: 1,
  motion: 'system',
  decimals: 1,
  sizeAttrs: false,
  namePattern: '{name}',
  maxSide: 8000,
  maxStaged: 100,
};
const KEY = 'pngsvg.prefs';

function load(): Prefs {
  try {
    const saved = JSON.parse(localStorage.getItem(KEY) ?? 'null');
    if (saved && typeof saved === 'object') {
      const p = { ...DEFAULTS, ...saved } as Prefs;
      if (p.theme !== 'system' && !(p.theme in themes)) p.theme = 'system';
      if (!TEXT_SCALES.includes(p.textScale)) p.textScale = 1;
      if (!MAX_SIDES.includes(p.maxSide)) p.maxSide = DEFAULTS.maxSide;
      if (!MAX_STAGED.includes(p.maxStaged)) p.maxStaged = DEFAULTS.maxStaged;
      p.decimals = Math.min(3, Math.max(0, Math.round(Number(p.decimals) || 0)));
      return p;
    }
  } catch {
    /* ignore */
  }
  return { ...DEFAULTS };
}

export const prefs = $state(load());

export function savePrefs(): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(prefs));
  } catch {
    /* ignore */
  }
  applyAppearance();
}

const dark = window.matchMedia?.('(prefers-color-scheme: dark)');

/** The theme actually shown ("system" follows the computer: light → paper, dark → lightbox). */
export function resolvedTheme(): keyof typeof themes {
  if (prefs.theme !== 'system') return prefs.theme;
  return dark?.matches ? 'lightbox' : 'paper';
}

export function applyAppearance(): void {
  const root = document.documentElement;
  const name = resolvedTheme();
  const theme = themes[name];
  for (const [k, v] of Object.entries(theme.tokens)) root.style.setProperty(`--${k}`, v);
  root.style.colorScheme = theme.scheme;
  root.dataset.theme = name;
  root.dataset.density = prefs.density;
  root.dataset.motion = prefs.motion;
  root.style.setProperty('--ts', String(prefs.textScale));
}

dark?.addEventListener('change', () => {
  if (prefs.theme === 'system') applyAppearance();
});

/** The part of the preferences the local service applies (limits, saved file names, SVG size attributes). */
export function servicePrefs() {
  return {
    name_pattern: prefs.namePattern,
    size_attrs: prefs.sizeAttrs,
    max_side: prefs.maxSide,
    max_staged: prefs.maxStaged,
  };
}

/** Preview of a saved file name for the pattern (mirrors the service's output_name). */
export function previewName(pattern: string, name: string, style: string): string {
  const stem = name.includes('.') ? name.slice(0, name.lastIndexOf('.')) : name;
  const date = new Date().toISOString().slice(0, 10);
  const out = (pattern || '{name}')
    .replace(/\{(name|nama)\}/g, stem)
    .replace(/\{(style|gaya)\}/g, style)
    .replace(/\{(date|tanggal)\}/g, date)
    .replace(/[\\/:*?"<>|]+/g, '-')
    .trim();
  return `${out || stem || 'image'}.svg`;
}
