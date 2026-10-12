#!/usr/bin/env bash
# Package the PyInstaller .app into a compressed DMG with an Applications shortcut (built-in hdiutil only).
#     packaging/macos/build_dmg.sh <version> <arch>      e.g. 1.0.0 arm64
set -euo pipefail

version="$1"
arch="$2"
app="dist/PNG to SVG Vectorize.app"
out="dist/PNG-to-SVG-Vectorize-${version}-${arch}.dmg"

[ -d "$app" ] || { echo "missing $app (run PyInstaller first)" >&2; exit 1; }

stage="$(mktemp -d)"
trap 'rm -rf "$stage"' EXIT
cp -R "$app" "$stage/"
ln -s /Applications "$stage/Applications"
rm -f "$out"
hdiutil create -volname "PNG to SVG Vectorize" -srcfolder "$stage" -fs HFS+ -format UDZO -ov "$out"
echo "$out"
