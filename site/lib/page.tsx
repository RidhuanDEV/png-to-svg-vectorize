// Shared page frame and metadata for the /en and /id pages.

import type { Metadata } from "next";
import { notFound } from "next/navigation";
import type { ReactNode } from "react";
import { href, SiteHeader, type PageKey } from "@/components/site-header";
import { SiteFooter } from "@/components/site-footer";
import { dict, isLang, LANGS, SITE_URL, type Lang } from "./site";

export const staticLangs = () => LANGS.map((lang) => ({ lang }));

/** The language of a route, or a 404 for anything else. */
export function langOf(v: string): Lang {
  if (!isLang(v)) notFound();
  return v;
}

export function pageMeta(lang: Lang, page: PageKey, title: string | null, description?: string): Metadata {
  const t = dict(lang);
  const full = title ? `${title} · PNG to SVG Vectorize` : t.meta.title;
  const desc = description ?? t.meta.description;
  const path = href(lang, page);
  return {
    title: full,
    description: desc,
    metadataBase: new URL(SITE_URL + "/"),
    alternates: {
      canonical: SITE_URL + path,
      languages: Object.fromEntries(LANGS.map((l) => [l, SITE_URL + href(l, page)])),
    },
    openGraph: {
      title: full,
      description: desc,
      url: SITE_URL + path,
      siteName: "PNG to SVG Vectorize",
      locale: lang === "id" ? "id_ID" : "en_US",
      type: "website",
      images: [{ url: SITE_URL + "/og.png", width: 1200, height: 630, alt: "PNG on the left, SVG on the right" }],
    },
    twitter: { card: "summary_large_image", title: full, description: desc, images: [SITE_URL + "/og.png"] },
  };
}

export function Shell({ lang, page, children }: { lang: Lang; page: PageKey; children: ReactNode }) {
  return (
    <>
      <SiteHeader lang={lang} page={page} />
      <main id="main" tabIndex={-1} className="outline-none">
        {children}
      </main>
      <SiteFooter lang={lang} />
    </>
  );
}

export function PageTitle({ title, lead }: { title: string; lead?: string }) {
  return (
    <div className="mx-auto max-w-6xl px-4 pt-14 pb-8 sm:px-6 sm:pt-20">
      <h1 className="max-w-3xl text-4xl font-semibold tracking-tight text-balance sm:text-5xl">{title}</h1>
      {lead && <p className="mt-4 max-w-2xl text-lg text-pretty text-muted-foreground">{lead}</p>}
    </div>
  );
}
