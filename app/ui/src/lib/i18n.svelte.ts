// Languages come from src/locales/<code>.json (English is the reference; "_name" is the language's own name).
// Adding a language = adding one file; scripts/check-locales.mjs makes sure it has every key and placeholder.
// Wording is for people who are not technical: say what happens and what to do next.

import en from '../locales/en.json';

type Dict = typeof en;
export type Key = Exclude<keyof Dict, '_name'>;
export type Lang = string;

const files = import.meta.glob<Dict>('../locales/*.json', { eager: true, import: 'default' });
const dicts: Record<Lang, Dict> = Object.fromEntries(
  Object.entries(files).map(([path, dict]) => [path.replace(/^.*\/(.+)\.json$/, '$1'), dict]),
);

/** Available languages, English first, then by name. */
export const languages = Object.entries(dicts)
  .map(([code, d]) => ({ value: code, label: d._name }))
  .sort((a, b) => (a.value === 'en' ? -1 : b.value === 'en' ? 1 : a.label.localeCompare(b.label)));

const KEY = 'pngsvg.lang';

function initial(): Lang {
  try {
    const saved = localStorage.getItem(KEY);
    if (saved && saved in dicts) return saved;
  } catch {
    /* ignore */
  }
  const nav = navigator.language.toLowerCase();
  return Object.keys(dicts).find((c) => nav === c || nav.startsWith(c + '-')) ?? 'en';
}

export const i18n = $state({ lang: initial() });

export function setLang(lang: Lang): void {
  if (!(lang in dicts)) return;
  i18n.lang = lang;
  document.documentElement.lang = lang;
  try {
    localStorage.setItem(KEY, lang);
  } catch {
    /* ignore */
  }
}

/** Missing keys in a contributed language fall back to English. */
export function t(key: Key): string {
  return dicts[i18n.lang]?.[key] ?? en[key];
}

/** Lookup by a computed key (status_*, stage_*, preset_*); unknown keys fall back to the key itself. */
export function tk(key: string): string {
  return (dicts[i18n.lang] as Record<string, string>)?.[key] ?? (en as Record<string, string>)[key] ?? key;
}

/** Text with {placeholders}. */
export function tf(key: Key, vars: Record<string, string | number>): string {
  return t(key).replace(/\{(\w+)\}/g, (_, k: string) => String(vars[k] ?? ''));
}
