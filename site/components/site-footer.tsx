import Link from "next/link";
import { BrandMark } from "@/components/brand";
import { href } from "@/components/site-header";
import { content, dict, fill, REPO_URL, type Lang } from "@/lib/site";

export function SiteFooter({ lang }: { lang: Lang }) {
  const t = dict(lang);
  const link = "text-muted-foreground transition-colors hover:text-foreground";
  return (
    <footer className="mt-24 border-t bg-card">
      <div className="mx-auto grid max-w-6xl gap-10 px-4 py-12 sm:px-6 md:grid-cols-[2fr_1fr_1fr]">
        <div>
          <div className="flex items-center gap-2.5 font-semibold">
            <BrandMark size={26} />
            PNG to SVG Vectorize
          </div>
          <p className="mt-3 max-w-sm text-sm text-muted-foreground">{t.footer.tagline}</p>
          <p className="mt-6 font-mono text-xs text-muted-foreground">
            {fill(t.footer.built, { v: content.version, d: content.builtAt })}
          </p>
        </div>
        <nav aria-label={t.footer.product} className="flex flex-col gap-2 text-sm">
          <span className="mb-1 font-semibold">{t.footer.product}</span>
          <Link className={link} href={href(lang, "features")}>{t.nav.features}</Link>
          <Link className={link} href={href(lang, "gallery")}>{t.nav.gallery}</Link>
          <Link className={link} href={href(lang, "download")}>{t.nav.download}</Link>
          <Link className={link} href={href(lang, "guide")}>{t.nav.guide}</Link>
          <Link className={link} href={href(lang, "changelog")}>{t.footer.changelog}</Link>
        </nav>
        <nav aria-label={t.footer.project} className="flex flex-col gap-2 text-sm">
          <span className="mb-1 font-semibold">{t.footer.project}</span>
          <a className={link} href={REPO_URL}>GitHub</a>
          <Link className={link} href={href(lang, "open-source")}>{t.footer.openSource}</Link>
          <Link className={link} href={href(lang, "privacy")}>{t.footer.privacy}</Link>
          <a className={link} href={`${REPO_URL}/blob/main/LICENSE`}>{t.footer.license}</a>
        </nav>
      </div>
    </footer>
  );
}
