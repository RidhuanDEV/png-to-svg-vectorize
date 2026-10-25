import { langOf, pageMeta, PageTitle, Shell, staticLangs } from "@/lib/page";
import { dict } from "@/lib/site";

export const generateStaticParams = staticLangs;

export async function generateMetadata({ params }: PageProps<"/[lang]/privacy">) {
  const lang = langOf((await params).lang);
  return pageMeta(lang, "privacy", dict(lang).privacy.title);
}

export default async function Privacy({ params }: PageProps<"/[lang]/privacy">) {
  const lang = langOf((await params).lang);
  const t = dict(lang).privacy;
  return (
    <Shell lang={lang} page="privacy">
      <PageTitle title={t.title} />
      <dl className="mx-auto max-w-3xl space-y-8 px-4 sm:px-6">
        {t.items.map(([name, body]) => (
          <div key={name} className="border-l-4 border-node pl-5">
            <dt className="text-lg font-semibold">{name}</dt>
            <dd className="mt-1 text-muted-foreground">{body}</dd>
          </div>
        ))}
      </dl>
    </Shell>
  );
}
