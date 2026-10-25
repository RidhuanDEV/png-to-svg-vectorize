import { GitHubMark } from "@/components/brand";
import Link from "next/link";
import { preload } from "react-dom";
import { ArrowRight, BadgeCheck, ChevronDown, Lock, Sparkles } from "lucide-react";
import { BeforeAfter } from "@/components/before-after";
import { DownloadButton } from "@/components/download-button";
import { GalleryCard } from "@/components/gallery-card";
import { href } from "@/components/site-header";
import { buttonVariants } from "@/components/ui/button";
import { choices } from "@/lib/downloads";
import { langOf, pageMeta, Shell, staticLangs } from "@/lib/page";
import { asset, dict, fill, gallery, REPO_URL } from "@/lib/site";
import { cn } from "@/lib/utils";

export const generateStaticParams = staticLangs;

export async function generateMetadata({ params }: PageProps<"/[lang]">) {
  return pageMeta(langOf((await params).lang), "home", null);
}

const PILLAR_ICONS = [Sparkles, Lock, BadgeCheck];

export default async function Home({ params }: PageProps<"/[lang]">) {
  const lang = langOf((await params).lang);
  const t = dict(lang);
  const hero = gallery.find((g) => g.name === "caticorn") ?? gallery[0];
  const heroImage = asset(`/gallery/${hero.name}-full.webp`);
  const heroSet = [480, 720, 960].map((w) => `${asset(`/gallery/${hero.name}-${w}.webp`)} ${w}w`).join(", ") + `, ${heroImage} ${hero.width}w`;
  const heroSizes = "(min-width: 1024px) 540px, 92vw";
  preload(heroImage, { as: "image", fetchPriority: "high", imageSrcSet: heroSet, imageSizes: heroSizes });
  return (
    <Shell lang={lang} page="home">
      <section className="grid-paper border-b">
        <div className="mx-auto grid max-w-6xl items-center gap-10 px-4 py-14 sm:px-6 lg:grid-cols-[1.05fr_1fr] lg:py-20">
          <div>
            <p className="font-mono text-xs font-semibold tracking-[0.18em] text-node uppercase">{t.home.eyebrow}</p>
            <h1 className="mt-4 text-4xl leading-[1.08] font-semibold tracking-tight text-balance sm:text-5xl lg:text-[3.4rem]">
              {t.home.title}
            </h1>
            <p className="mt-5 max-w-xl text-lg text-pretty text-muted-foreground">{t.home.lead}</p>
            <div className="mt-8 flex flex-wrap gap-3">
              <DownloadButton label={t.home.download} fallback={href(lang, "download")} choices={choices(lang)} size="xl" />
              <a href={REPO_URL} className={cn(buttonVariants({ variant: "outline", size: "lg" }), "h-12 px-5 text-base")}>
                <GitHubMark />
                {t.home.github}
              </a>
            </div>
          </div>
          <BeforeAfter
            original={heroImage}
            originalSrcSet={heroSet}
            sizes={heroSizes}
            vector={asset(`/gallery/${hero.name}.svg`)}
            width={hero.width}
            height={hero.height}
            priority
            labels={{ original: t.home.original, vector: t.home.vector, slider: t.home.sliderLabel, zoom: t.home.zoom, zoomHint: t.home.zoomHint }}
            caption={fill(t.home.measured, { sim: hero.similarity?.toFixed(2) ?? "—", kb: Math.round(hero.svgBytes / 1024) })}
          />
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-20 sm:px-6" aria-labelledby="pillars">
        <h2 id="pillars" className="text-3xl font-semibold tracking-tight">{t.home.pillarsTitle}</h2>
        <div className="mt-8 grid gap-5 md:grid-cols-3">
          {t.home.pillars.map((p, i) => {
            const Icon = PILLAR_ICONS[i];
            return (
              <div key={p.title} className="rounded-xl border bg-card p-6 shadow-sm">
                <span className="grid size-10 place-items-center rounded-lg bg-muted text-node">
                  <Icon className="size-5" aria-hidden="true" />
                </span>
                <h3 className="mt-4 text-lg font-semibold">{p.title}</h3>
                <p className="mt-2 text-muted-foreground">{p.body}</p>
              </div>
            );
          })}
        </div>
      </section>

      <section className="border-y bg-card" aria-labelledby="steps">
        <div className="mx-auto max-w-6xl px-4 py-20 sm:px-6">
          <h2 id="steps" className="text-3xl font-semibold tracking-tight">{t.home.stepsTitle}</h2>
          <ol className="mt-10 grid gap-8 md:grid-cols-4">
            {t.home.steps.map((s, i) => (
              <li key={s.title} className="relative">
                <span className="flex items-center gap-3">
                  <span className="grid size-9 place-items-center rounded-full border-2 border-node font-mono text-sm font-semibold">
                    {i + 1}
                  </span>
                  {i < 3 && <span className="hidden h-px flex-1 bg-line-strong md:block" aria-hidden="true" />}
                </span>
                <h3 className="mt-4 font-semibold">{s.title}</h3>
                <p className="mt-1.5 text-muted-foreground">{s.body}</p>
              </li>
            ))}
          </ol>
          {/* eslint-disable-next-line @next/next/no-img-element -- static export */}
          <img
            src={asset("/shots/app-overview-1360.webp")}
            srcSet={`${asset("/shots/app-overview-680.webp")} 680w, ${asset("/shots/app-overview-1360.webp")} 1360w`}
            sizes="(min-width: 1152px) 1104px, 92vw"
            alt="PNG to SVG Vectorize: original and SVG side by side"
            width={1360}
            height={820}
            loading="lazy"
            className="mt-14 w-full rounded-xl border shadow-lg"
          />
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-20 sm:px-6" aria-labelledby="gallery">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h2 id="gallery" className="text-3xl font-semibold tracking-tight">{t.home.galleryTitle}</h2>
            <p className="mt-3 max-w-2xl text-muted-foreground">{t.home.galleryLead}</p>
          </div>
          <Link href={href(lang, "gallery")} className={buttonVariants({ variant: "outline", size: "lg" })}>
            {t.home.galleryMore}
            <ArrowRight aria-hidden="true" />
          </Link>
        </div>
        <div className="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {gallery.slice(1, 5).map((g) => (
            <GalleryCard key={g.name} item={g} lang={lang} />
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-3xl px-4 py-12 sm:px-6" aria-labelledby="faq">
        <h2 id="faq" className="text-3xl font-semibold tracking-tight">{t.home.faqTitle}</h2>
        <div className="mt-6 divide-y border-y">
          {t.home.faq.map((f) => (
            <details key={f.q} className="group py-1">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-4 rounded-md py-3 text-base font-medium hover:underline [&::-webkit-details-marker]:hidden">
                {f.q}
                <ChevronDown className="size-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-180" aria-hidden="true" />
              </summary>
              <p className="pb-4 text-muted-foreground">{f.a}</p>
            </details>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 pt-12 sm:px-6">
        <div className="grid-paper flex flex-col items-start gap-5 rounded-2xl border bg-card p-8 shadow-sm sm:p-12 md:flex-row md:items-center md:justify-between">
          <div>
            <h2 className="text-3xl font-semibold tracking-tight">{t.home.ctaTitle}</h2>
            <p className="mt-2 text-muted-foreground">{t.home.ctaBody}</p>
          </div>
          <DownloadButton label={t.home.download} fallback={href(lang, "download")} choices={choices(lang)} size="xl" />
        </div>
      </section>
    </Shell>
  );
}
