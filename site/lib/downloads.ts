// Release files grouped by system, from the latest GitHub release (src/generated/content.json).

import type { Choice } from "@/components/download-button";
import { content, type Lang, type ReleaseAsset, dict } from "./site";

export interface Platform {
  key: "windows" | "mac-arm" | "mac-intel";
  title: string;
  files: (ReleaseAsset & { label: string })[];
}

export function platforms(lang: Lang): Platform[] {
  const t = dict(lang).download;
  const assets = content.release?.assets ?? [];
  const find = (re: RegExp) => assets.filter((a) => re.test(a.name));
  const list: Platform[] = [
    {
      key: "windows",
      title: t.windows,
      files: [
        ...find(/Setup-.*\.exe$/).map((a) => ({ ...a, label: t.winSetup })),
        ...find(/windows-x64-portable\.zip$/).map((a) => ({ ...a, label: t.winZip })),
      ],
    },
    { key: "mac-arm", title: t.macArm, files: find(/arm64\.dmg$/).map((a) => ({ ...a, label: "DMG" })) },
    { key: "mac-intel", title: t.macIntel, files: find(/x64\.dmg$/).map((a) => ({ ...a, label: "DMG" })) },
  ];
  return list.filter((p) => p.files.length);
}

/** One recommended file per system for the main download button. */
export function choices(lang: Lang): Choice[] {
  return platforms(lang).map((p) => ({ os: p.key, url: p.files[0].url, label: p.title.split(" — ").pop() ?? p.title }));
}
