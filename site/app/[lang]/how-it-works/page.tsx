import { GitHubMark } from "@/components/brand";
import { buttonVariants } from "@/components/ui/button";
import { langOf, pageMeta, PageTitle, Shell, staticLangs } from "@/lib/page";
import { dict, REPO_URL } from "@/lib/site";

export const generateStaticParams = staticLangs;

export async function generateMetadata({ params }: PageProps<"/[lang]/how-it-works">) {
  const lang = langOf((await params).lang);
  return pageMeta(lang, "how-it-works", dict(lang).how.title, dict(lang).how.lead);
}

/** The pipeline as pen nodes on one curve, in the theme's colors. */
function Pipeline({ steps, label }: { steps: string[]; label: string }) {
  const w = 960;
  const x = (i: number) => 60 + (i * (w - 120)) / (steps.length - 1);
  return (
    <svg viewBox={`0 0 ${w} 150`} role="img" aria-label={label} className="h-auto w-full">
      <path
        d={`M ${x(0)} 70 C ${x(1)} 10, ${x(2)} 130, ${x(3)} 70 S ${x(5) - 60} 20, ${x(5)} 70`}
        className="fill-none stroke-line-strong"
        strokeWidth="2"
        strokeDasharray="6 6"
      />
      {steps.map((s, i) => (
        <g key={s}>
          <circle cx={x(i)} cy={70} r={i === steps.length - 1 ? 13 : 10} className={i === steps.length - 1 ? "fill-node" : "fill-card stroke-node"} strokeWidth="3" />
          <text x={x(i)} y={118} textAnchor="middle" className="fill-foreground text-[15px] font-semibold">
            {s}
          </text>
        </g>
      ))}
    </svg>
  );
}

export default async function How({ params }: PageProps<"/[lang]/how-it-works">) {
  const lang = langOf((await params).lang);
  const t = dict(lang).how;
  return (
    <Shell lang={lang} page="how-it-works">
      <PageTitle title={t.title} lead={t.lead} />
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <div className="rounded-2xl border bg-card p-4 shadow-sm sm:p-8">
          <Pipeline steps={t.pipeline} label={t.pipelineLabel} />
        </div>
        <section aria-labelledby="simple" className="mt-14 max-w-3xl">
          <h2 id="simple" className="text-2xl font-semibold tracking-tight">{t.simpleTitle}</h2>
          <ol className="mt-6 space-y-5">
            {t.simple.map((p, i) => (
              <li key={i} className="flex gap-4">
                <span className="grid size-8 shrink-0 place-items-center rounded-full border-2 border-node font-mono text-sm font-semibold">{i + 1}</span>
                <p className="pt-0.5 text-lg text-pretty">{p}</p>
              </li>
            ))}
          </ol>
        </section>
        <section aria-labelledby="tech" className="mt-16">
          <h2 id="tech" className="text-2xl font-semibold tracking-tight">{t.techTitle}</h2>
          <dl className="mt-6 grid gap-5 md:grid-cols-2 lg:grid-cols-3">
            {t.tech.map(([name, body]) => (
              <div key={name} className="rounded-xl border bg-card p-5 shadow-sm">
                <dt className="font-mono text-sm font-semibold text-node">{name}</dt>
                <dd className="mt-2 text-muted-foreground">{body}</dd>
              </div>
            ))}
          </dl>
          <a href={`${REPO_URL}/tree/main/src/pngsvg`} className={buttonVariants({ variant: "outline", size: "lg" }) + " mt-8"}>
            <GitHubMark />
            {t.source}
          </a>
        </section>
      </div>
    </Shell>
  );
}
