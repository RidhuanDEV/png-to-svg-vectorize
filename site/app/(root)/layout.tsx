import "../globals.css";
import { fontVars } from "../fonts";
import type { Metadata } from "next";
import type { ReactNode } from "react";
import { asset } from "@/lib/site";

export const metadata: Metadata = {
  title: "PNG to SVG Vectorize",
  icons: { icon: [{ url: asset("/favicon.svg"), type: "image/svg+xml" }] },
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={fontVars}>
      <body className="min-h-dvh">{children}</body>
    </html>
  );
}
