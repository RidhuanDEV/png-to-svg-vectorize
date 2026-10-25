import "../globals.css";
import { fontVars } from "../fonts";
import type { Metadata, Viewport } from "next";
import { asset } from "@/lib/site";
import { langOf, staticLangs } from "@/lib/page";

export const dynamicParams = false;
export const generateStaticParams = staticLangs;

export const metadata: Metadata = {
  icons: { icon: [{ url: asset("/favicon.svg"), type: "image/svg+xml" }], apple: asset("/icon-256.png") },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#F3EEE4" },
    { media: "(prefers-color-scheme: dark)", color: "#141312" },
  ],
};

export default async function LangLayout({ children, params }: LayoutProps<"/[lang]">) {
  const lang = langOf((await params).lang);
  return (
    <html lang={lang} className={fontVars}>
      <body className="min-h-dvh">{children}</body>
    </html>
  );
}
