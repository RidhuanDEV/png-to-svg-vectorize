import type { MetadataRoute } from "next";
import { href, type PageKey } from "@/components/site-header";
import { LANGS, SITE_URL } from "@/lib/site";

export const dynamic = "force-static";

const PAGES: PageKey[] = ["home", "features", "how-it-works", "gallery", "compare", "download", "guide", "changelog", "open-source", "privacy"];

export default function sitemap(): MetadataRoute.Sitemap {
  return PAGES.flatMap((page) =>
    LANGS.map((lang) => ({
      url: SITE_URL + href(lang, page),
      alternates: { languages: Object.fromEntries(LANGS.map((l) => [l, SITE_URL + href(l, page)])) },
    })),
  );
}
