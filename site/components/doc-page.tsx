import type { Heading } from "@/lib/markdown";

/** Rendered repository Markdown with an on-page table of contents. The HTML comes from our own reviewed files. */
export function DocPage({ html, headings, note }: { html: string; headings: Heading[]; note?: string }) {
  return (
    <div className="mx-auto grid max-w-6xl gap-10 px-4 pt-10 sm:px-6 lg:grid-cols-[220px_minmax(0,1fr)]">
      <nav aria-label="Contents" className="hidden lg:block">
        <ul className="sticky top-24 space-y-1 border-l text-sm">
          {headings.map((h) => (
            <li key={h.id}>
              <a href={`#${h.id}`} className="-ml-px block border-l border-transparent py-1 pl-4 text-muted-foreground hover:border-node hover:text-foreground">
                {h.text}
              </a>
            </li>
          ))}
        </ul>
      </nav>
      <article className="min-w-0">
        {note && <p className="mb-6 rounded-lg border bg-card p-3 text-sm text-muted-foreground">{note}</p>}
        <div className="prose-doc" dangerouslySetInnerHTML={{ __html: html }} />
      </article>
    </div>
  );
}
