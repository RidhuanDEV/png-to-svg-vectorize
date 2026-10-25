import { GitHubMark } from "@/components/brand";
import { buttonVariants } from "@/components/ui/button";
import { langOf, pageMeta, PageTitle, Shell, staticLangs } from "@/lib/page";
import { dict, REPO_URL } from "@/lib/site";

export const generateStaticParams = staticLangs;

export async function generateMetadata({ params }: PageProps<"/[lang]/open-source">) {
  const lang = langOf((await params).lang);
  return pageMeta(lang, "open-source", dict(lang).openSource.title, dict(lang).openSource.lead);
}

export default async function OpenSource({ params }: PageProps<"/[lang]/open-source">) {
  const lang = langOf((await params).lang);
  const t = dict(lang).openSource;
  return (
    <Shell lang={lang} page="open-source">
      <PageTitle title={t.title} lead={t.lead} />
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <a href={REPO_URL} className={buttonVariants({ size: "lg" }) + " h-11 px-5"}>
          <GitHubMark />
          RidhuanDEV/png-to-svg-vectorize
        </a>
        <dl className="mt-10 grid gap-5 md:grid-cols-2">
          {t.items.map(([name, body]) => (
            <div key={name} className="rounded-xl border bg-card p-6 shadow-sm">
              <dt className="font-semibold">{name}</dt>
              <dd className="mt-2 text-muted-foreground">{body}</dd>
            </div>
          ))}
        </dl>
        <div className="mt-14 grid gap-10 md:grid-cols-2">
          <section aria-labelledby="lic">
            <h2 id="lic" className="text-xl font-semibold">{t.licenses}</h2>
            <table className="mt-4 w-full text-sm">
              <tbody>
                {t.licenseList.map(([name, lic]) => (
                  <tr key={name} className="border-b">
                    <th scope="row" className="py-2 pr-4 text-left font-normal text-muted-foreground">{name}</th>
                    <td className="py-2 font-mono">{lic}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
          <section aria-labelledby="road">
            <h2 id="road" className="text-xl font-semibold">{t.roadmap}</h2>
            <p className="mt-4 text-muted-foreground">{t.roadmapBody}</p>
          </section>
        </div>
      </div>
    </Shell>
  );
}
