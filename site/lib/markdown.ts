// Markdown from the repository (guide, changelog) rendered to HTML at build time. The source is our own reviewed
// repository text; relative links are pointed at GitHub and screenshots at this site.

import { Marked } from "marked";
import { asset, REPO_URL } from "./site";

export interface Heading {
  id: string;
  text: string;
}

const slug = (s: string) =>
  s
    .toLowerCase()
    .replace(/<[^>]+>/g, "")
    .replace(/[^\p{L}\p{N}]+/gu, "-")
    .replace(/^-|-$/g, "");

/** `dir`: the folder of the Markdown file in the repository ("" for the root, "docs" for the guides). */
export function renderMarkdown(md: string, dir: string): { html: string; headings: Heading[] } {
  const headings: Heading[] = [];
  const resolve = (href: string): string => {
    if (/^(https?:|mailto:|#)/.test(href)) return href;
    const parts = [...(dir ? dir.split("/") : []), ...href.split("/")];
    const out: string[] = [];
    for (const p of parts) {
      if (p === "..") out.pop();
      else if (p !== ".") out.push(p);
    }
    const path = out.join("/");
    if (path.startsWith("docs/images/") && path.endsWith(".png")) {
      return asset("/shots/" + path.slice("docs/images/".length).replace(/\.png$/, "-1360.webp"));
    }
    return `${REPO_URL}/blob/main/${path}`;
  };
  const marked = new Marked({
    gfm: true,
    walkTokens(token) {
      if (token.type === "link" || token.type === "image") token.href = resolve(token.href);
    },
    renderer: {
      heading({ tokens, depth }) {
        const text = this.parser.parseInline(tokens);
        const id = slug(text);
        if (depth === 2) headings.push({ id, text: text.replace(/<[^>]+>/g, "") });
        return `<h${depth} id="${id}">${text}</h${depth}>\n`;
      },
      link({ href, title, tokens }) {
        const text = this.parser.parseInline(tokens);
        const external = /^https?:/.test(href);
        const t = title ? ` title="${title}"` : "";
        return `<a href="${href}"${t}${external ? ' rel="noopener"' : ""}>${text}</a>`;
      },
      image({ href, text }) {
        // screenshots: responsive WebP made by scripts/assets.py
        const set = href.endsWith("-1360.webp") ? ` srcset="${href.replace("-1360.webp", "-680.webp")} 680w, ${href} 1360w" sizes="(min-width: 1152px) 830px, 92vw"` : "";
        return `<img src="${href}"${set} alt="${text}" width="1360" height="820" loading="lazy" decoding="async">`;
      },
    },
  });
  const html = marked.parse(md, { async: false });
  return { html, headings };
}
