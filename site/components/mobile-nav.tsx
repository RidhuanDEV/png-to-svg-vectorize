import { Languages, Menu, X } from "lucide-react";
import { cn } from "@/lib/utils";

interface Props {
  label: string;
  items: { href: string; label: string; current: boolean }[];
  language: { href: string; label: string; lang: string };
}

/** Small-screen menu without JavaScript: a native disclosure; links load the next page fresh. */
export function MobileNav({ label, items, language }: Props) {
  return (
    <details className="group relative md:hidden">
      <summary
        aria-label={label}
        className="grid size-10 cursor-pointer list-none place-items-center rounded-lg hover:bg-muted [&::-webkit-details-marker]:hidden"
      >
        <Menu className="size-5 group-open:hidden" aria-hidden="true" />
        <X className="hidden size-5 group-open:block" aria-hidden="true" />
      </summary>
      <nav aria-label={label} className="absolute top-12 right-0 z-50 flex w-64 flex-col gap-1 rounded-xl border bg-popover p-2 shadow-lg">
        {items.map((i) => (
          <a
            key={i.href}
            href={i.href}
            aria-current={i.current ? "page" : undefined}
            className={cn("rounded-md px-3 py-2.5 hover:bg-muted", i.current && "bg-muted font-semibold")}
          >
            {i.label}
          </a>
        ))}
        <a href={language.href} hrefLang={language.lang} lang={language.lang} className="mt-1 flex items-center gap-2 rounded-md border px-3 py-2.5">
          <Languages className="size-4" aria-hidden="true" />
          {language.label}
        </a>
      </nav>
    </details>
  );
}
