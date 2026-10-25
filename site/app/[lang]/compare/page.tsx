import { langOf, pageMeta, PageTitle, Shell, staticLangs } from "@/lib/page";
import { dict, E7_MEDIAN, fill, REPO_URL } from "@/lib/site";

export const generateStaticParams = staticLangs;

export async function generateMetadata({ params }: PageProps<"/[lang]/compare">) {
  const lang = langOf((await params).lang);
  return pageMeta(lang, "compare", dict(lang).compare.title, dict(lang).compare.lead);
}

export default async function Compare({ params }: PageProps<"/[lang]/compare">) {
  const lang = langOf((await params).lang);
  const t = dict(lang).compare;
  return (
    <Shell lang={lang} page="compare">
      <PageTitle title={t.title} lead={t.lead} />
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <section aria-labelledby="glance">
          <h2 id="glance" className="text-2xl font-semibold tracking-tight">{t.tableTitle}</h2>
          <div className="mt-6 overflow-x-auto rounded-xl border bg-card shadow-sm">
            <table className="w-full min-w-[760px] text-left text-sm">
              <thead>
                <tr className="border-b bg-muted">
                  {t.cols.map((c, i) => (
                    <th key={i} scope="col" className={i === 1 ? "px-4 py-3 font-semibold text-foreground" : "px-4 py-3 font-semibold text-muted-foreground"}>
                      {c}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {t.rows.map(([name, ...cells]) => (
                  <tr key={name} className="border-b last:border-0">
                    <th scope="row" className="px-4 py-3 font-medium">{name}</th>
                    {cells.map((c, i) => (
                      <td key={i} className={i === 0 ? "bg-muted/60 px-4 py-3 font-semibold" : "px-4 py-3 text-muted-foreground"}>
                        {c}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-3 text-sm text-muted-foreground">{t.note}</p>
        </section>
        <div className="mt-16 grid gap-10 md:grid-cols-2">
          <section aria-labelledby="ours" className="rounded-xl border bg-card p-6 shadow-sm">
            <h2 id="ours" className="text-xl font-semibold">{t.numbersTitle}</h2>
            <p className="mt-3 font-mono text-4xl font-semibold text-node">{E7_MEDIAN.toFixed(2)} %</p>
            <p className="mt-3 text-muted-foreground">{fill(t.numbers, { sim: E7_MEDIAN.toFixed(2) })}</p>
            <a className="mt-4 inline-block text-sm font-medium underline underline-offset-4" href={`${REPO_URL}/blob/main/docs/bench.md`}>
              docs/bench.md
            </a>
          </section>
          <section aria-labelledby="method">
            <h2 id="method" className="text-xl font-semibold">{t.methodTitle}</h2>
            <ol className="mt-4 list-decimal space-y-3 pl-5 text-muted-foreground">
              {t.method.map((m) => (
                <li key={m}>{m}</li>
              ))}
            </ol>
            <a className="mt-4 inline-block text-sm font-medium underline underline-offset-4" href={`${REPO_URL}/blob/main/docs/compare-tools.md`}>
              docs/compare-tools.md
            </a>
          </section>
        </div>
      </div>
    </Shell>
  );
}
