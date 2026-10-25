import { BeforeAfter } from "@/components/before-after";
import { Badge } from "@/components/ui/badge";
import { langOf, pageMeta, PageTitle, Shell, staticLangs } from "@/lib/page";
import { asset, dict, gallery, kb } from "@/lib/site";

export const generateStaticParams = staticLangs;

export async function generateMetadata({ params }: PageProps<"/[lang]/gallery">) {
  const lang = langOf((await params).lang);
  return pageMeta(lang, "gallery", dict(lang).gallery.title, dict(lang).gallery.lead);
}

export default async function Gallery({ params }: PageProps<"/[lang]/gallery">) {
  const lang = langOf((await params).lang);
  const t = dict(lang);
  const g = t.gallery;
  return (
    <Shell lang={lang} page="gallery">
      <PageTitle title={g.title} lead={g.lead} />
      <div className="mx-auto grid max-w-6xl gap-14 px-4 sm:px-6 lg:grid-cols-2">
        {gallery.map((item, i) => (
          <article key={item.name} id={item.name} className="scroll-mt-24">
            <BeforeAfter
              original={asset(`/gallery/${item.name}-960.webp`)}
              originalSrcSet={[480, 720, 960].map((w) => `${asset(`/gallery/${item.name}-${w}.webp`)} ${w}w`).join(", ")}
              sizes="(min-width: 1024px) 560px, 92vw"
              priority={i === 0}
              vector={asset(`/gallery/${item.name}.svg`)}
              width={item.width}
              height={item.height}
              labels={{ original: t.home.original, vector: t.home.vector, slider: t.home.sliderLabel, zoom: t.home.zoom, zoomHint: t.home.zoomHint }}
            />
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <h2 className="mr-auto font-semibold">{item.title}</h2>
              <Badge variant="secondary">{g.styles[item.style]}</Badge>
            </div>
            <dl className="mt-3 grid grid-cols-3 gap-3 rounded-lg border bg-card p-3 text-center">
              <div>
                <dt className="text-xs text-muted-foreground">{g.similarity}</dt>
                <dd className="font-mono font-semibold">{item.similarity?.toFixed(2)} %</dd>
              </div>
              <div>
                <dt className="text-xs text-muted-foreground">{g.svgSize}</dt>
                <dd className="font-mono font-semibold">{kb(item.svgBytes)}</dd>
              </div>
              <div>
                <dt className="text-xs text-muted-foreground">{g.time}</dt>
                <dd className="font-mono font-semibold">{item.seconds.toFixed(1)} s</dd>
              </div>
            </dl>
            <p className="mt-2 text-xs text-muted-foreground">
              {item.artist ? `${g.by} ${item.artist} · ` : ""}
              <a href={item.page} className="underline underline-offset-2">
                Wikimedia Commons
              </a>{" "}
              · {item.license}
            </p>
          </article>
        ))}
      </div>
      <p className="mx-auto mt-12 max-w-6xl px-4 text-sm text-muted-foreground sm:px-6">{g.method}</p>
    </Shell>
  );
}
