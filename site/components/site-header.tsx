import Link from "next/link";
import { Download, Languages } from "lucide-react";
import { BrandMark } from "@/components/brand";
import { MobileNav } from "@/components/mobile-nav";
import { buttonVariants } from "@/components/ui/button";
import { BASE_PATH, dict, type Lang } from "@/lib/site";
import { cn } from "@/lib/utils";

export type PageKey = "home" | "features" | "how-it-works" | "gallery" | "compare" | "guide" | "download" | "changelog" | "open-source" | "privacy";

export const href = (lang: Lang, page: PageKey) => (page === "home" ? `/${lang}/` : `/${lang}/${page}/`);

export function SiteHeader({ lang, page }: { lang: Lang; page: PageKey }) {
  const t = dict(lang);
  const other: Lang = lang === "en" ? "id" : "en";
  const items: [PageKey, string][] = [
    ["features", t.nav.features],
    ["how-it-works", t.nav.how],
    ["gallery", t.nav.gallery],
    ["compare", t.nav.compare],
    ["guide", t.nav.guide],
  ];
  const all: [PageKey, string][] = [...items, ["download", t.nav.download]];
  return (
    <header className="sticky top-0 z-40 border-b bg-background/85 backdrop-blur supports-[backdrop-filter]:bg-background/70">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:rounded-md focus:bg-card focus:px-3 focus:py-2">
        {t.nav.skip}
      </a>
      <div className="mx-auto flex h-16 max-w-6xl items-center gap-6 px-4 sm:px-6">
        <Link href={href(lang, "home")} className="flex items-center gap-2.5 font-semibold tracking-tight">
          <BrandMark />
          <span>PNG to SVG Vectorize</span>
        </Link>
        <nav aria-label="Main" className="ml-2 hidden items-center gap-1 text-sm md:flex">
          {items.map(([key, label]) => (
            <Link
              key={key}
              href={href(lang, key)}
              aria-current={page === key ? "page" : undefined}
              className={cn(
                "rounded-md px-3 py-2 text-muted-foreground transition-colors hover:text-foreground",
                page === key && "text-foreground shadow-[inset_0_-2px_0_var(--t-node)]",
              )}
            >
              {label}
            </Link>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-2">
          <Link
            href={href(other, page)}
            hrefLang={other}
            lang={other}
            className={cn(buttonVariants({ variant: "ghost", size: "sm" }), "hidden sm:inline-flex")}
          >
            <Languages aria-hidden="true" />
            {t.nav.language}
          </Link>
          <Link href={href(lang, "download")} className={cn(buttonVariants({ size: "lg" }), "hidden px-4 sm:inline-flex")}>
            <Download aria-hidden="true" />
            {t.nav.download}
          </Link>
          <MobileNav
            label={t.nav.menu}
            items={all.map(([key, label]) => ({ href: BASE_PATH + href(lang, key), label, current: page === key }))}
            language={{ href: BASE_PATH + href(other, page), label: t.nav.language, lang: other }}
          />
        </div>
      </div>
    </header>
  );
}
