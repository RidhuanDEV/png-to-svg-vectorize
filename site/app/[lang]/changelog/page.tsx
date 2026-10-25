import { DocPage } from "@/components/doc-page";
import { renderMarkdown } from "@/lib/markdown";
import { langOf, pageMeta, Shell, staticLangs } from "@/lib/page";
import { content, dict } from "@/lib/site";

export const generateStaticParams = staticLangs;

export async function generateMetadata({ params }: PageProps<"/[lang]/changelog">) {
  const lang = langOf((await params).lang);
  return pageMeta(lang, "changelog", dict(lang).changelog.title);
}

export default async function Changelog({ params }: PageProps<"/[lang]/changelog">) {
  const lang = langOf((await params).lang);
  const { html, headings } = renderMarkdown(content.changelog, "");
  return (
    <Shell lang={lang} page="changelog">
      <DocPage html={html} headings={headings} note={dict(lang).changelog.note || undefined} />
    </Shell>
  );
}
