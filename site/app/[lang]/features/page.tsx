import { Check } from "lucide-react";
import { langOf, pageMeta, PageTitle, Shell, staticLangs } from "@/lib/page";
import { asset, dict } from "@/lib/site";
import { SCREENSHOTS } from "@/lib/screenshots";

export const generateStaticParams = staticLangs;

export async function generateMetadata({ params }: PageProps<"/[lang]/features">) {
  const lang = langOf((await params).lang);
  return pageMeta(lang, "features", dict(lang).features.title, dict(lang).features.lead);
}

export default async function Features({ params }: PageProps<"/[lang]/features">) {
  const lang = langOf((await params).lang);
  const t = dict(lang).features;
  return (
    <Shell lang={lang} page="features">
      <PageTitle title={t.title} lead={t.lead} />
      <div className="mx-auto max-w-6xl space-y-14 px-4 sm:px-6">
        {t.groups.map((g) => (
          <section key={g.title} aria-labelledby={`g-${g.title}`} className="grid gap-6 border-t pt-10 md:grid-cols-[220px_1fr]">
            <h2 id={`g-${g.title}`} className="text-xl font-semibold">{g.title}</h2>
            <dl className="grid gap-x-8 gap-y-6 sm:grid-cols-2">
              {g.items.map(([name, body]) => (
                <div key={name}>
                  <dt className="flex items-center gap-2.5 font-semibold">
                    <Check className="size-4 shrink-0 text-node" aria-hidden="true" />
                    {name}
                  </dt>
                  <dd className="mt-1 pl-[26px] text-muted-foreground">{body}</dd>
                </div>
              ))}
            </dl>
          </section>
        ))}
        <section aria-labelledby="shots" className="border-t pt-10">
          <h2 id="shots" className="text-xl font-semibold">{t.screenshots}</h2>
          <div className="mt-6 grid gap-8 md:grid-cols-2">
            {t.shots.map(([file, caption]) => (
              <figure key={file}>
                {/* eslint-disable-next-line @next/next/no-img-element -- static export */}
                <img
                  src={asset(`/shots/${file.replace(".png", "-1360.webp")}`)}
                  srcSet={`${asset(`/shots/${file.replace(".png", "-680.webp")}`)} 680w, ${asset(`/shots/${file.replace(".png", "-1360.webp")}`)} 1360w`}
                  sizes="(min-width: 768px) 540px, 92vw"
                  alt={caption}
                  width={SCREENSHOTS[file]?.[0]}
                  height={SCREENSHOTS[file]?.[1]}
                  loading="lazy"
                  className="w-full rounded-xl border shadow-md"
                />
                <figcaption className="mt-2 text-sm text-muted-foreground">{caption}</figcaption>
              </figure>
            ))}
          </div>
        </section>
      </div>
    </Shell>
  );
}
