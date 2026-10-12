// Two languages, picked from the browser language and switchable by the user (remembered locally).

const en = {
  appName: 'PNG to SVG Vectorize',
  tagline: 'Raster illustrations to clean, editable SVG. Everything stays on this computer.',
  drop: 'Drop PNG, WebP or JPEG images here',
  orOpen: 'or',
  open: 'Open images…',
  queue: 'Images',
  emptyQueue: 'No images yet.',
  status_queued: 'Waiting',
  status_running: 'Working',
  status_done: 'Done',
  status_error: 'Failed',
  status_cancelled: 'Cancelled',
  stage_ink: 'finding outlines',
  stage_regions: 'finding color regions',
  stage_curves: 'fitting curves',
  stage_svg: 'writing SVG',
  cancel: 'Cancel',
  retry: 'Run again',
  remove: 'Remove',
  settings: 'Settings',
  preset: 'Preset',
  preset_cartoon: 'Cartoon',
  preset_flat: 'Flat illustration',
  preset_logo: 'Logo / icon',
  preset_poster: 'Photo → poster',
  advanced: 'Advanced',
  opt_outlines: 'Separate ink outlines',
  opt_gradients: 'Gradient fills',
  opt_radial: 'Radial gradients',
  opt_tolerance: 'Curve tolerance (px)',
  opt_smooth: 'Smoothing (px)',
  opt_merge_de: 'Merge similar colors (ΔE)',
  opt_scale: 'Outline detail (upscale)',
  auto: 'auto',
  resetPreset: 'Reset to preset',
  applySelected: 'Re-process selected image',
  newUploadsUse: 'New images use these settings.',
  compare: 'Compare',
  sideBySide: 'Side by side',
  slider: 'Slider',
  layers: 'Layers',
  layer_all: 'All',
  layer_fill: 'Fills only',
  layer_outline: 'Outlines only',
  zoomIn: 'Zoom in',
  zoomOut: 'Zoom out',
  fit: 'Fit',
  original: 'Original',
  vector: 'SVG',
  selectHint: 'Add an image to start. Scroll to zoom, drag to pan.',
  notReady: 'The SVG appears here when it is done.',
  result: 'Result',
  similarity: 'Similarity',
  regions: 'Regions',
  gradients: 'Gradients',
  outlines: 'Outline shapes',
  size: 'SVG size',
  time: 'Time',
  measuring: 'measuring…',
  export: 'Export',
  saveSvg: 'Save SVG',
  saveAll: 'Save all',
  copySvg: 'Copy SVG code',
  copied: 'Copied',
  language: 'Language',
  noToken: 'This page needs the link printed by "png2svg serve" (it contains the session key). Open that link again.',
  rejected: 'Not accepted',
  privacy: 'Local only · no uploads · no tracking',
};

type Dict = typeof en;

const id: Dict = {
  appName: 'PNG to SVG Vectorize',
  tagline: 'Ilustrasi raster menjadi SVG yang rapi dan bisa diedit. Semua tetap di komputer ini.',
  drop: 'Seret gambar PNG, WebP, atau JPEG ke sini',
  orOpen: 'atau',
  open: 'Buka gambar…',
  queue: 'Gambar',
  emptyQueue: 'Belum ada gambar.',
  status_queued: 'Menunggu',
  status_running: 'Diproses',
  status_done: 'Selesai',
  status_error: 'Gagal',
  status_cancelled: 'Dibatalkan',
  stage_ink: 'mencari garis tinta',
  stage_regions: 'mencari wilayah warna',
  stage_curves: 'menyusun kurva',
  stage_svg: 'menulis SVG',
  cancel: 'Batal',
  retry: 'Proses lagi',
  remove: 'Hapus',
  settings: 'Pengaturan',
  preset: 'Preset',
  preset_cartoon: 'Kartun',
  preset_flat: 'Ilustrasi datar',
  preset_logo: 'Logo / ikon',
  preset_poster: 'Foto → poster',
  advanced: 'Lanjutan',
  opt_outlines: 'Pisahkan garis tinta',
  opt_gradients: 'Isian gradien',
  opt_radial: 'Gradien radial',
  opt_tolerance: 'Toleransi kurva (px)',
  opt_smooth: 'Penghalusan (px)',
  opt_merge_de: 'Gabung warna mirip (ΔE)',
  opt_scale: 'Detail garis (pembesaran)',
  auto: 'otomatis',
  resetPreset: 'Kembalikan ke preset',
  applySelected: 'Proses ulang gambar terpilih',
  newUploadsUse: 'Gambar baru memakai pengaturan ini.',
  compare: 'Bandingkan',
  sideBySide: 'Berdampingan',
  slider: 'Geser',
  layers: 'Lapisan',
  layer_all: 'Semua',
  layer_fill: 'Isian saja',
  layer_outline: 'Garis saja',
  zoomIn: 'Perbesar',
  zoomOut: 'Perkecil',
  fit: 'Pas',
  original: 'Asli',
  vector: 'SVG',
  selectHint: 'Tambahkan gambar untuk mulai. Gulir untuk zoom, seret untuk geser.',
  notReady: 'SVG muncul di sini setelah selesai.',
  result: 'Hasil',
  similarity: 'Kemiripan',
  regions: 'Wilayah',
  gradients: 'Gradien',
  outlines: 'Bentuk garis',
  size: 'Ukuran SVG',
  time: 'Waktu',
  measuring: 'mengukur…',
  export: 'Ekspor',
  saveSvg: 'Simpan SVG',
  saveAll: 'Simpan semua',
  copySvg: 'Salin kode SVG',
  copied: 'Tersalin',
  language: 'Bahasa',
  noToken: 'Halaman ini perlu tautan yang dicetak oleh "png2svg serve" (berisi kunci sesi). Buka tautan itu lagi.',
  rejected: 'Tidak diterima',
  privacy: 'Lokal saja · tanpa unggahan · tanpa pelacakan',
};

export type Lang = 'en' | 'id';
const dicts: Record<Lang, Dict> = { en, id };
const KEY = 'pngsvg.lang';

function initial(): Lang {
  try {
    const saved = localStorage.getItem(KEY);
    if (saved === 'en' || saved === 'id') return saved;
  } catch {
    /* ignore */
  }
  return navigator.language.toLowerCase().startsWith('id') ? 'id' : 'en';
}

export const i18n = $state({ lang: initial() });

export function setLang(lang: Lang): void {
  i18n.lang = lang;
  document.documentElement.lang = lang;
  try {
    localStorage.setItem(KEY, lang);
  } catch {
    /* ignore */
  }
}

export function t(key: keyof Dict): string {
  return dicts[i18n.lang][key];
}

export function tk(key: string): string {
  return (dicts[i18n.lang] as Record<string, string>)[key] ?? key;
}
