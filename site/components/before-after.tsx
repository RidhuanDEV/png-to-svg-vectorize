"use client";

// Before/after slider: the original raster under the SVG, a draggable divider (also a keyboard-operable range input)
// and a zoom that follows the pointer — at 4× the PNG shows its pixels while the SVG stays sharp.

import { ZoomIn, ZoomOut } from "lucide-react";
import { useRef, useState, type PointerEvent } from "react";
import { cn } from "@/lib/utils";

interface Props {
  original: string;
  /** responsive candidates of the original, e.g. "a-480.webp 480w, a-960.webp 960w" */
  originalSrcSet?: string;
  sizes?: string;
  vector: string;
  width: number;
  height: number;
  labels: { original: string; vector: string; slider: string; zoom: string; zoomHint: string };
  caption?: string;
  priority?: boolean;
}

export function BeforeAfter({ original, originalSrcSet, sizes, vector, width, height, labels, caption, priority = false }: Props) {
  const [pos, setPos] = useState(50);
  const [zoom, setZoom] = useState(1);
  const [origin, setOrigin] = useState({ x: 50, y: 40 });
  const box = useRef<HTMLDivElement>(null);
  const dragging = useRef(false);

  const where = (e: PointerEvent<HTMLDivElement>) => {
    const r = box.current?.getBoundingClientRect();
    if (!r) return null;
    return { x: ((e.clientX - r.left) / r.width) * 100, y: ((e.clientY - r.top) / r.height) * 100 };
  };
  const clamp = (v: number) => Math.min(100, Math.max(0, v));

  const transform = { transform: `scale(${zoom})`, transformOrigin: `${origin.x}% ${origin.y}%` };
  const img = "absolute inset-0 size-full object-contain transition-transform duration-300 ease-out select-none";

  return (
    <figure className="w-full">
      <div
        ref={box}
        className="checker relative w-full cursor-ew-resize touch-none overflow-hidden rounded-xl border shadow-sm"
        style={{ aspectRatio: `${width} / ${height}` }}
        onPointerDown={(e) => {
          dragging.current = true;
          e.currentTarget.setPointerCapture(e.pointerId);
          const p = where(e);
          if (p) setPos(clamp(p.x));
        }}
        onPointerMove={(e) => {
          const p = where(e);
          if (!p) return;
          if (dragging.current) setPos(clamp(p.x));
          else if (zoom > 1) setOrigin({ x: clamp(p.x), y: clamp(p.y) });
        }}
        onPointerUp={() => (dragging.current = false)}
        onPointerCancel={() => (dragging.current = false)}
      >
        {/* eslint-disable-next-line @next/next/no-img-element -- static export: plain images */}
        <img
          src={original}
          srcSet={originalSrcSet}
          sizes={sizes}
          alt=""
          width={width}
          height={height}
          draggable={false}
          className={cn(img, zoom > 1 && "[image-rendering:pixelated]")}
          style={transform}
          fetchPriority={priority ? "high" : "auto"}
          loading={priority ? "eager" : "lazy"}
        />
        <div className="absolute inset-0" style={{ clipPath: `inset(0 0 0 ${pos}%)` }}>
          {/* eslint-disable-next-line @next/next/no-img-element -- the SVG is shown as an image, never inlined */}
          <img src={vector} alt="" width={width} height={height} draggable={false} className={img} style={transform} loading={priority ? "eager" : "lazy"} fetchPriority="low" />
        </div>
        <div className="pointer-events-none absolute inset-y-0 w-0.5 bg-node" style={{ left: `${pos}%` }} aria-hidden="true">
          <span className="absolute top-1/2 left-1/2 grid size-9 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full border-2 border-node bg-card shadow">
            <span className="size-2 rounded-full bg-node" />
          </span>
        </div>
        <span className="absolute top-3 left-3 rounded-md bg-card/90 px-2 py-1 font-mono text-xs font-semibold shadow-sm">
          {labels.original}
        </span>
        <span className="absolute top-3 right-3 rounded-md bg-card/90 px-2 py-1 font-mono text-xs font-semibold shadow-sm">
          {labels.vector}
        </span>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-3">
        <label className="flex min-w-48 flex-1 items-center gap-3 text-sm">
          <span className="sr-only">{labels.slider}</span>
          <input
            type="range"
            min={0}
            max={100}
            value={Math.round(pos)}
            onChange={(e) => setPos(Number(e.target.value))}
            className="w-full accent-[var(--t-node)]"
            aria-label={labels.slider}
          />
        </label>
        <button
          type="button"
          onClick={() => setZoom(zoom > 1 ? 1 : 4)}
          aria-pressed={zoom > 1}
          className="inline-flex h-9 items-center gap-2 rounded-lg border bg-card px-3 text-sm font-medium transition-colors hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50"
        >
          {zoom > 1 ? <ZoomOut className="size-4" aria-hidden="true" /> : <ZoomIn className="size-4" aria-hidden="true" />}
          {labels.zoom} {zoom > 1 ? "4×" : "1×"}
        </button>
      </div>
      <figcaption className="mt-2 text-sm text-muted-foreground">
        {zoom > 1 ? labels.zoomHint : caption}
      </figcaption>
    </figure>
  );
}
