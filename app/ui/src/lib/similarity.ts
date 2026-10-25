// Similarity score computed in the page (no browser automation needed): both images are drawn to a canvas at
// the same size and compared like pngsvg.compare.similarity: 100 - mean absolute RGB error in %.

const MAX_SIDE = 1024; // measured on a downscaled copy: fast, and stable enough for a score

function load(url: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error('image failed to load'));
    img.src = url;
  });
}

/** `box`: where to draw the image (default: the whole canvas). */
function pixels(img: HTMLImageElement, w: number, h: number, box?: [number, number, number, number]): Uint8ClampedArray {
  const c = document.createElement('canvas');
  c.width = w;
  c.height = h;
  const ctx = c.getContext('2d', { willReadFrequently: true });
  if (!ctx) throw new Error('canvas unavailable');
  ctx.fillStyle = '#fff';
  ctx.fillRect(0, 0, w, h);
  if (box) ctx.drawImage(img, box[0], box[1], box[2], box[3]);
  else ctx.drawImage(img, 0, 0, w, h);
  return ctx.getImageData(0, 0, w, h).data;
}

/** `crop`: a trimmed SVG (logo engine) is placed back where it sits on the photo, in photo pixels. */
export async function similarity(
  sourceUrl: string,
  svgUrl: string,
  width: number,
  height: number,
  crop?: [number, number, number, number] | null,
): Promise<number> {
  const k = Math.min(1, MAX_SIDE / Math.max(width, height));
  const w = Math.max(1, Math.round(width * k));
  const h = Math.max(1, Math.round(height * k));
  const [a, b] = await Promise.all([load(sourceUrl), load(svgUrl)]);
  const pa = pixels(a, w, h);
  const pb = pixels(b, w, h, crop ? [crop[0] * k, crop[1] * k, crop[2] * k, crop[3] * k] : undefined);
  let sum = 0;
  for (let i = 0; i < pa.length; i += 4) {
    sum += Math.abs(pa[i] - pb[i]) + Math.abs(pa[i + 1] - pb[i + 1]) + Math.abs(pa[i + 2] - pb[i + 2]);
  }
  return 100 * (1 - sum / (w * h * 3) / 255);
}
