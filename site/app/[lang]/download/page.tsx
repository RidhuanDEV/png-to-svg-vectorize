import { GitHubMark } from "@/components/brand";
import { Apple, Download as DownloadIcon, MonitorDown, ShieldCheck } from "lucide-react";
import { DownloadButton } from "@/components/download-button";
import { href } from "@/components/site-header";
import { buttonVariants } from "@/components/ui/button";
import { choices, platforms } from "@/lib/downloads";
import { langOf, pageMeta, PageTitle, Shell, staticLangs } from "@/lib/page";
import { content, dict, fill, kb, REPO_URL } from "@/lib/site";

export const generateStaticParams = staticLangs;

export async function generateMetadata({ params }: PageProps<"/[lang]/download">) {
  const lang = langOf((await params).lang);
  return pageMeta(lang, "download", dict(lang).download.title, fill(dict(lang).download.lead, { v: content.version }));
}

export default async function Download({ params }: PageProps<"/[lang]/download">) {
  const lang = langOf((await params).lang);
  const t = dict(lang).download;
  const list = platforms(lang);
  const version = content.release?.tag.replace(/^v/, "") ?? content.version;
  return (
    <Shell lang={lang} page="download">
      <PageTitle title={t.title} lead={fill(t.lead, { v: version })} />
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        {list.length ? (
          <>
            <div className="flex flex-wrap items-center gap-4">
              <DownloadButton label={t.recommended} fallback={href(lang, "download")} choices={choices(lang)} size="xl" />
              {content.release && (
                <a href={content.release.url} className={buttonVariants({ variant: "outline", size: "lg" }) + " h-12 px-5"}>
                  <GitHubMark />
                  {t.allFiles}
                </a>
              )}
            </div>
            <div className="mt-10 grid gap-5 lg:grid-cols-3">
              {list.map((p) => (
                <section key={p.key} aria-labelledby={p.key} className="flex flex-col rounded-xl border bg-card p-6 shadow-sm">
                  <h2 id={p.key} className="flex items-center gap-2 font-semibold">
                    {p.key === "windows" ? <MonitorDown className="size-5 text-node" aria-hidden="true" /> : <Apple className="size-5 text-node" aria-hidden="true" />}
                    {p.title}
                  </h2>
                  <ul className="mt-4 flex flex-1 flex-col gap-4">
                    {p.files.map((f) => (
                      <li key={f.name}>
                        <a href={f.url} className="flex items-center justify-between gap-3 rounded-lg border px-3 py-2.5 font-medium transition-colors hover:bg-muted">
                          <span className="flex items-center gap-2">
                            <DownloadIcon className="size-4" aria-hidden="true" />
                            {f.label}
                          </span>
                          <span className="font-mono text-xs text-muted-foreground">{kb(f.size)}</span>
                        </a>
                        <p className="mt-1.5 truncate font-mono text-[11px] text-muted-foreground" title={f.sha256 ?? undefined}>
                          {f.name}
                        </p>
                        {f.sha256 && (
                          <p className="font-mono text-[11px] break-all text-muted-foreground">
                            <span className="font-semibold">{t.checksum}</span> {f.sha256}
                          </p>
                        )}
                      </li>
                    ))}
                  </ul>
                </section>
              ))}
            </div>
          </>
        ) : (
          <div className="rounded-xl border bg-card p-6">
            <p>{t.noRelease}</p>
            <a href={`${REPO_URL}#install`} className={buttonVariants({ size: "lg" }) + " mt-4"}>
              {t.fromSource}
            </a>
          </div>
        )}

        <section aria-labelledby="warn" className="mt-16 grid gap-8 md:grid-cols-2">
          <div className="md:col-span-2">
            <h2 id="warn" className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
              <ShieldCheck className="size-6 text-node" aria-hidden="true" />
              {t.unsigned}
            </h2>
            <p className="mt-2 max-w-3xl text-muted-foreground">{t.unsignedBody}</p>
          </div>
          <div className="rounded-xl border bg-card p-6">
            <h3 className="font-semibold">Windows</h3>
            <ol className="mt-3 list-decimal space-y-2 pl-5 text-muted-foreground">
              {t.winSteps.map((s) => <li key={s}>{s}</li>)}
            </ol>
          </div>
          <div className="rounded-xl border bg-card p-6">
            <h3 className="font-semibold">macOS</h3>
            <ol className="mt-3 list-decimal space-y-2 pl-5 break-words text-muted-foreground">
              {t.macSteps.map((s) => <li key={s}>{s}</li>)}
            </ol>
          </div>
          <div className="rounded-xl border bg-card p-6">
            <h3 className="font-semibold">{t.verifyTitle}</h3>
            <p className="mt-3 font-mono text-sm break-all">{t.verifyWin}</p>
            <p className="mt-2 font-mono text-sm break-all">{t.verifyMac}</p>
          </div>
          <div className="rounded-xl border bg-card p-6">
            <h3 className="font-semibold">{t.requirements}</h3>
            <ul className="mt-3 list-disc space-y-2 pl-5 text-muted-foreground">
              {t.req.map((r) => <li key={r}>{r}</li>)}
            </ul>
          </div>
        </section>

        <section aria-labelledby="cli" className="mt-16">
          <h2 id="cli" className="text-2xl font-semibold tracking-tight">{t.cli}</h2>
          <p className="mt-2 text-muted-foreground">{t.cliBody}</p>
          <pre className="mt-4 overflow-x-auto rounded-xl border bg-card p-4 font-mono text-sm">
            {`pip install "png-to-svg-vectorize @ git+${REPO_URL}"\npng2svg picture.png -o picture.pdf --max-colors 8`}
          </pre>
        </section>
      </div>
    </Shell>
  );
}
