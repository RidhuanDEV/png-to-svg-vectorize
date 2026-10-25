import { DocPage } from "@/components/doc-page";
import { renderMarkdown } from "@/lib/markdown";
import { langOf, pageMeta, Shell, staticLangs } from "@/lib/page";
import { content, dict } from "@/lib/site";

export const generateStaticParams = staticLangs;

export async function generateMetadata({ params }: PageProps<"/[lang]/guide">) {
  const lang = langOf((await params).lang);
  return pageMeta(lang, "guide", dict(lang).guide.title);
}

export default async function Guide({ params }: PageProps<"/[lang]/guide">) {
  const lang = langOf((await params).lang);
  const { html, headings } = renderMarkdown(content.guide[lang], "docs");
  return (
    <Shell lang={lang} page="guide">
      <DocPage html={html} headings={headings} note={dict(lang).guide.source} />
    </Shell>
  );
}
