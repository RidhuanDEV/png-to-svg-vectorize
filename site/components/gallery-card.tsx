import Link from "next/link";
import { href } from "@/components/site-header";
import { asset, dict, kb, type GalleryItem, type Lang } from "@/lib/site";

export function GalleryCard({ item, lang }: { item: GalleryItem; lang: Lang }) {
  const t = dict(lang).gallery;
  return (
    <Link
      href={`${href(lang, "gallery")}#${item.name}`}
      className="group overflow-hidden rounded-xl border bg-card shadow-sm transition-shadow hover:shadow-md focus-visible:ring-3 focus-visible:ring-ring/50"
    >
      <div className="checker aspect-[4/3] overflow-hidden">
        {/* eslint-disable-next-line @next/next/no-img-element -- the SVG result itself, shown as an image */}
        <img
          src={asset(`/gallery/${item.name}.svg`)}
          alt={item.title}
          width={item.previewWidth}
          height={item.previewHeight}
          loading="lazy"
          className="size-full object-contain p-3 transition-transform duration-300 group-hover:scale-[1.03]"
        />
      </div>
      <div className="flex items-center justify-between gap-2 border-t px-4 py-3 text-sm">
        <span className="truncate font-medium">{t.styles[item.style]}</span>
        <span className="shrink-0 font-mono text-xs text-muted-foreground">
          {item.similarity?.toFixed(2)} % · {kb(item.svgBytes)}
        </span>
      </div>
    </Link>
  );
}
