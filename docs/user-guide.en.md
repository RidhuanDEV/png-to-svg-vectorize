# PNG to SVG Vectorize — user guide

Turn raster illustrations (PNG, WebP, JPEG) into clean, editable SVG files: smooth gradient fills, crisp outlines,
pure `<path>` shapes that work in browsers, Figma, Illustrator, Inkscape and app frameworks. Everything happens on
your computer — nothing is uploaded, nothing is tracked.

*Bahasa Indonesia: [user-guide.id.md](user-guide.id.md)*

![Main window](images/app-overview.png)

## 1. Install

Download the latest release from the
[GitHub Releases page](https://github.com/RidhuanDEV/png-to-svg-vectorize/releases).

### Windows 10 / 11 (64-bit)

1. Download `PNG-to-SVG-Vectorize-Setup-x.y.z.exe` and run it. It installs for your user only; no administrator
   rights are needed.
2. The app is free and open source and is **not code-signed**, so Windows SmartScreen may show
   *"Windows protected your PC"*. Click **More info → Run anyway**.
3. The app needs the Microsoft Edge **WebView2 Runtime**. It is built into Windows 11 and almost every Windows 10. If
   the installer says it is missing, install the *Evergreen Runtime* from
   <https://developer.microsoft.com/microsoft-edge/webview2/>.

Prefer no installer? Use `PNG-to-SVG-Vectorize-x.y.z-windows-x64-portable.zip`: unzip anywhere and run
`PNG to SVG Vectorize.exe`.

### macOS 12 or newer

1. Download the DMG for your Mac: `…-arm64.dmg` for Apple Silicon (M1 and later), `…-x64.dmg` for Intel Macs.
2. Open it and drag **PNG to SVG Vectorize** into **Applications**.
3. The app is **not notarized** by Apple, so the first launch is blocked. Open **System Settings → Privacy & Security**,
   scroll down and click **Open Anyway** next to the message about PNG to SVG Vectorize, then confirm. (On macOS 14 and
   older, right-click the app → **Open** also works.)
4. If macOS says the app "is damaged and can't be opened", remove the download quarantine flag in Terminal:

   ```bash
   xattr -dr com.apple.quarantine "/Applications/PNG to SVG Vectorize.app"
   ```

## 2. Convert images

1. **Add images**: drag one or more PNG, WebP or JPEG files anywhere into the window, or click **Open images…**.
   Limits: 50 MB per file, at most 8000 px on the longest side.
2. Each image appears in the **Images** list with its progress (finding outlines → finding color regions → fitting
   curves → writing SVG). A typical 1536×1024 illustration takes 5–10 seconds; several images are processed in
   parallel.
3. Click an image in the list to show it. Use ■ to cancel, ↻ to run again, ✕ to remove it.

## 3. Compare original and SVG

- **Side by side**: original on the left, SVG on the right. Scroll to zoom (up to 800 %), drag to pan — both sides
  move together. **Fit** (or the `0` key) shows the whole image; `+` / `-` and arrow keys work too.
- **Slider**: one view with a divider; drag the handle (or use ← →) to wipe between original and SVG.
- **Layers**: show *All*, *Fills only* or *Outlines only* to check each part of the SVG.
- **Result** shows the **similarity** (how close the SVG looks to the original, 100 % = identical; good results are
  around 98–99 %), the number of regions, gradients and outline shapes, the file size and the time.

Always check details at 200 % or more: one number can hide a small local defect.

## 4. Settings

**Presets** — pick the one that matches the picture before adding images (or re-process later):

| Preset | Use for |
|---|---|
| Cartoon | character art with dark ink outlines and soft shading (default) |
| Flat illustration | solid shapes with few outlines; only clear gradients are kept |
| Logo / icon | few flat colors and exact geometry; no gradients |
| Photo → poster | photos or paintings turned into a poster-like vector with fewer, larger regions |

**Advanced** settings (change them, then click **Re-process selected image**):

| Setting | Effect |
|---|---|
| Separate ink outlines | dark outlines become their own crisp layer |
| Gradient fills / Radial gradients | smooth shading as gradients; off = flat colors |
| Curve tolerance | larger = fewer curve points and smaller files, smaller = closer to the pixels |
| Smoothing | larger = smoother boundaries between colors |
| Merge similar colors (ΔE) | larger = fewer regions (simpler), smaller = more detail |
| Outline detail | resolution used to trace the outlines (auto is usually right) |

New images always use the current settings. **Reset to preset** brings the defaults back.

## 5. Save

- **Save SVG** saves the selected result (the app asks where).
- **Save all** saves every finished result into a folder you choose; existing files are never overwritten
  (`name-2.svg` is used instead).
- **Copy SVG code** puts the SVG markup on the clipboard, ready to paste into code or a design tool.

Gradient ids are unique per file, so many SVGs can be inlined on one web page.

## 6. Tips for the best result

- Clean illustrations work best: cartoons, flat art, icons, logos. Photos produce many regions (use *Photo → poster*).
- Use the largest, sharpest version you have (around 1000–2000 px on the long side). Avoid heavily compressed JPEGs:
  their noise turns into tiny regions.
- If small details disappear, lower *Merge similar colors*; if the file is too big, raise *Curve tolerance*.

## 7. Privacy

The app starts a small service inside itself that only accepts connections from the same computer
(`127.0.0.1`) and only with a random key created for each session. Images and results are kept in memory and are
gone when you close the app. There is no telemetry and no network access to anything outside your computer.

## 8. Troubleshooting

| Problem | Fix |
|---|---|
| Windows: blank window or the app closes immediately | Install the WebView2 Runtime (see Install). |
| Windows: antivirus quarantines the app | Unsigned apps built with PyInstaller are sometimes flagged. Restore it and add an exception, or build it yourself from source. |
| macOS: "can't be opened" / "damaged" | See Install, steps 3–4. |
| "Not accepted — 413" | The file is larger than 50 MB or 8000 px; scale it down. |
| "Not accepted — 415" | Not a PNG, WebP or JPEG image (the file content is checked, not the name). |
| Something else went wrong | The app writes a log: Windows `%LOCALAPPDATA%\PNG to SVG Vectorize\app.log`, macOS `~/Library/Application Support/PNG to SVG Vectorize/app.log`. Please attach it to a [GitHub issue](https://github.com/RidhuanDEV/png-to-svg-vectorize/issues) (it contains no image data). |

## 9. Command line and Python

The same engine is available without the app (Python 3.10+):
`pip install "png-to-svg-vectorize @ git+https://github.com/RidhuanDEV/png-to-svg-vectorize"`, then
`png2svg picture.png`. See the [README](../README.md) for options, the browser UI (`png2svg serve`) and the
Python API.
