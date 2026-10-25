// Site-wide constants, languages and content loaded at build time.

import contentJson from "@/src/generated/content.json";
import galleryJson from "@/src/generated/gallery.json";
import { en, type Dict } from "@/src/i18n/en";
import { id } from "@/src/i18n/id";

export const REPO_URL = "https://github.com/RidhuanDEV/png-to-svg-vectorize";
export const SITE_URL = "https://ridhuandev.github.io/png-to-svg-vectorize";
export const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH ?? "";

export const LANGS = ["en", "id"] as const;
export type Lang = (typeof LANGS)[number];

export function isLang(v: string): v is Lang {
  return (LANGS as readonly string[]).includes(v);
}

const DICTS: Record<Lang, Dict> = { en, id };
export const dict = (lang: Lang): Dict => DICTS[lang];

/** A file in /public (plain <img>/<a> do not get the basePath automatically). */
export const asset = (path: string): string => `${BASE_PATH}${path}`;

/** "{n} files" -> "3 files" */
export function fill(template: string, values: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (m, k: string) => (k in values ? String(values[k]) : m));
}

export interface ReleaseAsset {
  name: string;
  size: number;
  url: string;
  sha256: string | null;
}

export interface Release {
  tag: string;
  date: string;
  url: string;
  assets: ReleaseAsset[];
}

export interface Content {
  version: string;
  changelog: string;
  guide: Record<Lang, string>;
  release: Release | null;
  builtAt: string;
}

export interface GalleryItem {
  name: string;
  file: string;
  category: string;
  style: "cartoon" | "flat" | "logo" | "poster";
  title: string;
  artist: string;
  license: string;
  page: string;
  width: number;
  height: number;
  previewWidth: number;
  previewHeight: number;
  similarity: number | null;
  svgBytes: number;
  sourceBytes: number;
  seconds: number;
  regions: number;
  gradients: number;
}

// generated files are validated at this boundary instead of trusted by a type cast
const isObj = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);
const str = (v: unknown, what: string): string => {
  if (typeof v !== "string") throw new Error(`content: ${what} must be text`);
  return v;
};
const num = (v: unknown, what: string): number => {
  if (typeof v !== "number") throw new Error(`content: ${what} must be a number`);
  return v;
};
const STYLES = ["cartoon", "flat", "logo", "poster"] as const;

function toRelease(v: unknown): Release | null {
  if (v === null || v === undefined) return null;
  if (!isObj(v) || !Array.isArray(v.assets)) throw new Error("content: bad release");
  return {
    tag: str(v.tag, "release.tag"),
    date: str(v.date, "release.date"),
    url: str(v.url, "release.url"),
    assets: v.assets.map((a: unknown) => {
      if (!isObj(a)) throw new Error("content: bad asset");
      return { name: str(a.name, "asset.name"), size: num(a.size, "asset.size"), url: str(a.url, "asset.url"), sha256: a.sha256 === null ? null : str(a.sha256, "asset.sha256") };
    }),
  };
}

function toContent(v: unknown): Content {
  if (!isObj(v) || !isObj(v.guide)) throw new Error("content.json: run npm run content");
  return {
    version: str(v.version, "version"),
    changelog: str(v.changelog, "changelog"),
    guide: { en: str(v.guide.en, "guide.en"), id: str(v.guide.id, "guide.id") },
    release: toRelease(v.release),
    builtAt: str(v.builtAt, "builtAt"),
  };
}

function toGallery(v: unknown): GalleryItem[] {
  if (!Array.isArray(v)) throw new Error("gallery.json must be a list");
  return v.map((g: unknown) => {
    if (!isObj(g)) throw new Error("gallery: bad item");
    const style = STYLES.find((s) => s === g.style);
    if (!style) throw new Error("gallery: bad style");
    return {
      name: str(g.name, "name"), file: str(g.file, "file"), category: str(g.category, "category"), style,
      title: str(g.title, "title"), artist: str(g.artist, "artist"), license: str(g.license, "license"),
      page: str(g.page, "page"), width: num(g.width, "width"), height: num(g.height, "height"),
      previewWidth: num(g.previewWidth, "previewWidth"), previewHeight: num(g.previewHeight, "previewHeight"),
      similarity: g.similarity === null ? null : num(g.similarity, "similarity"), svgBytes: num(g.svgBytes, "svgBytes"),
      sourceBytes: num(g.sourceBytes, "sourceBytes"), seconds: num(g.seconds, "seconds"), regions: num(g.regions, "regions"),
      gradients: num(g.gradients, "gradients"),
    };
  });
}

export const content: Content = toContent(contentJson);
export const gallery: GalleryItem[] = toGallery(galleryJson);

/** Median similarity on the 27-image comparison set (docs/bench.md, v1.0 table; unchanged since). */
export const E7_MEDIAN = 99.72;

export const kb = (bytes: number): string => (bytes >= 1048576 ? `${(bytes / 1048576).toFixed(1)} MB` : `${Math.round(bytes / 1024)} KB`);
