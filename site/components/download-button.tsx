"use client";

// The main download button: the installer for the visitor's system (detected in the browser), else the download page.

import Link from "next/link";
import { Download } from "lucide-react";
import { useEffect, useState } from "react";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export interface Choice {
  os: "windows" | "mac-arm" | "mac-intel";
  url: string;
  label: string;
}

/** CPU architecture from User-Agent Client Hints (Chromium browsers); null where unsupported. */
async function clientHintArch(): Promise<string | null> {
  const data: unknown = Reflect.get(navigator, "userAgentData");
  if (typeof data !== "object" || data === null) return null;
  const fn: unknown = Reflect.get(data, "getHighEntropyValues");
  if (typeof fn !== "function") return null;
  try {
    const values: unknown = await fn.call(data, ["architecture"]);
    const arch: unknown = typeof values === "object" && values !== null ? Reflect.get(values, "architecture") : null;
    return typeof arch === "string" ? arch : null;
  } catch {
    return null;
  }
}

async function detect(): Promise<Choice["os"] | null> {
  const ua = navigator.userAgent;
  if (/Windows/i.test(ua)) return "windows";
  if (!/Mac OS X|Macintosh/i.test(ua)) return null;
  // every Mac browser says "Intel"; ask the client hints, else (Safari) the WebGL renderer
  const arch = await clientHintArch();
  if (arch) return arch === "arm" ? "mac-arm" : "mac-intel";
  const gl = document.createElement("canvas").getContext("webgl");
  const renderer: unknown = gl?.getParameter(gl.RENDERER);
  return typeof renderer === "string" && /Apple M|Apple GPU/i.test(renderer) ? "mac-arm" : "mac-intel";
}

let detection: Promise<Choice["os"] | null> | null = null; // once per page, shared by every button

export function DownloadButton({ label, fallback, choices, size = "lg" }: { label: string; fallback: string; choices: Choice[]; size?: "lg" | "xl" }) {
  const [os, setOs] = useState<Choice["os"] | null>(null);
  useEffect(() => {
    let live = true;
    detection ??= detect();
    void detection.then((v) => live && setOs(v));
    return () => {
      live = false;
    };
  }, []);
  const pick = choices.find((c) => c.os === os);
  const cls = cn(buttonVariants({ size: "lg" }), size === "xl" ? "h-12 px-6 text-base" : "h-11 px-5 text-[15px]");
  if (!pick) {
    return (
      <Link href={fallback} className={cls}>
        <Download aria-hidden="true" />
        {label}
      </Link>
    );
  }
  return (
    <a href={pick.url} className={cls}>
      <Download aria-hidden="true" />
      {label}
      <span className="font-normal opacity-80">· {pick.label}</span>
    </a>
  );
}
