// IBM Plex (SIL OFL), the app's typefaces, self-hosted through next/font: the files are preloaded and a metric-matched
// fallback is generated, so text does not jump when the web font arrives.

import localFont from "next/font/local";

export const plexSans = localFont({
  src: [{ path: "../node_modules/@fontsource-variable/ibm-plex-sans/files/ibm-plex-sans-latin-wght-normal.woff2", weight: "100 700", style: "normal" }],
  variable: "--font-plex-sans",
  display: "swap",
  adjustFontFallback: "Arial",
  fallback: ["ui-sans-serif", "system-ui", "Segoe UI", "sans-serif"],
});

export const plexMono = localFont({
  src: [
    { path: "../node_modules/@fontsource/ibm-plex-mono/files/ibm-plex-mono-latin-400-normal.woff2", weight: "400", style: "normal" },
    { path: "../node_modules/@fontsource/ibm-plex-mono/files/ibm-plex-mono-latin-600-normal.woff2", weight: "600", style: "normal" },
  ],
  variable: "--font-plex-mono",
  display: "swap",
  preload: false,
  adjustFontFallback: "Arial",
  fallback: ["ui-monospace", "Cascadia Mono", "monospace"],
});

export const fontVars = `${plexSans.variable} ${plexMono.variable}`;
