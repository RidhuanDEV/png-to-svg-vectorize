// "/" picks the visitor's language (Indonesian browsers -> /id/, everyone else -> /en/). Without JavaScript the
// meta refresh goes to English, and both links stay visible.

import { BrandMark } from "@/components/brand";
import { BASE_PATH, dict } from "@/lib/site";

const pick = `(function(){var l=(navigator.languages&&navigator.languages[0])||navigator.language||"";location.replace("${BASE_PATH}/"+(/^(id|ms)/i.test(l)?"id":"en")+"/")})()`;

export default function Root() {
  return (
    <>
      <meta httpEquiv="refresh" content={`2;url=${BASE_PATH}/en/`} />
      <script dangerouslySetInnerHTML={{ __html: pick }} />
      <main className="grid min-h-dvh place-items-center p-6">
        <div className="flex flex-col items-center gap-4 text-center">
          <BrandMark size={48} />
          <h1 className="text-2xl font-semibold">PNG to SVG Vectorize</h1>
          <p className="text-muted-foreground">
            {dict("en").root.choose} · {dict("id").root.choose}
          </p>
          <div className="flex gap-3">
            <a className="rounded-lg border bg-card px-4 py-2 font-medium" href={`${BASE_PATH}/en/`} hrefLang="en">
              English
            </a>
            <a className="rounded-lg border bg-card px-4 py-2 font-medium" href={`${BASE_PATH}/id/`} hrefLang="id">
              Bahasa Indonesia
            </a>
          </div>
        </div>
      </main>
    </>
  );
}
