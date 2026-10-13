// Two languages, picked from the browser language and switchable by the user (remembered locally).
// Wording is for people who are not technical: say what happens and what to do next.

const en = {
  appName: 'PNG to SVG Vectorize',
  tagline: 'Raster illustrations to clean, editable SVG. Everything stays on this computer.',
  privacy: 'Works offline · your photos never leave this computer',
  language: 'Language',
  help: 'Guide',
  noToken: 'This page needs the link printed by "png2svg serve" (it contains the session key). Open that link again.',

  step_add: 'Add photos',
  step_pick: 'Choose & set up',
  step_queue: 'Process',
  step_save: 'Compare & save',

  addTitle: 'Add photos to get started',
  addBody: 'Drag pictures here or choose them from your computer. You can add many at once — nothing is processed until you press Process.',
  addButton: 'Choose photos',
  addMore: 'Add more',
  formats: 'PNG, WebP or JPEG · up to 50 MB each',
  drop: 'Drop to add these photos',

  workbench: 'Workbench',
  pickTitle: 'Choose the photos to process',
  pickHint: 'Untick the ones you want to leave for later.',
  selectAll: 'Select all',
  selectNone: 'Clear',
  selectedCount: '{n} of {m} selected',
  processOne: 'Process 1 photo',
  processMany: 'Process {n} photos',
  processNone: 'Select photos to process',
  removeFromBench: 'Remove from workbench',
  benchEmpty: 'Your workbench is empty.',

  queueTitle: 'In progress',
  waitingPos: 'Waiting · #{n} in line',
  stopAll: 'Stop all',
  resultsTitle: 'Results',
  status_staged: 'Ready',
  status_queued: 'Waiting',
  status_running: 'Working',
  status_done: 'Done',
  status_error: "Couldn't convert",
  status_cancelled: 'Stopped',
  stage_start: 'starting',
  stage_ink: 'reading the outlines',
  stage_regions: 'splitting the colors',
  stage_curves: 'smoothing the curves',
  stage_svg: 'building the SVG',
  cancel: 'Stop',
  retry: 'Run again',
  remove: 'Remove',
  failedHelp: "This photo couldn't be converted. Try another style or run it again.",

  speed: 'Processing speed',
  speed_auto: 'Automatic',
  speed_saver: 'Saver',
  speed_balanced: 'Balanced',
  speed_fast: 'Fast',
  speedHelp_auto: 'Picked for this computer: {mode} ({n} at a time).',
  speedHelp_saver: 'One photo at a time with low priority — your computer stays smooth.',
  speedHelp_balanced: 'Two photos at a time on capable computers ({n} here).',
  speedHelp_fast: 'Up to {n} photos at a time. Best when you are not using the computer for anything else.',

  style: 'Result style',
  styleNote: 'Used for the photos you process next.',
  preset_cartoon: 'Cartoon',
  preset_flat: 'Flat illustration',
  preset_logo: 'Logo / icon',
  preset_poster: 'Photo → poster',
  desc_cartoon: 'Drawings with dark outlines',
  desc_flat: 'Flat colors, no outlines',
  desc_logo: 'Few colors, sharp edges',
  desc_poster: 'Photos as a simplified poster',
  advanced: 'Fine-tune',
  opt_outlines: 'Separate ink outlines',
  opt_gradients: 'Gradient fills',
  opt_radial: 'Radial gradients',
  opt_tolerance: 'Curve tolerance (px)',
  opt_smooth: 'Smoothing (px)',
  opt_merge_de: 'Merge similar colors (ΔE)',
  opt_scale: 'Outline detail (upscale)',
  auto: 'auto',
  resetPreset: 'Reset to style defaults',
  reprocess: 'Process again with this style',

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
  selectHint: 'Pick a finished photo on the left to compare it here. Scroll to zoom, drag to move.',
  notReady: 'The SVG appears here when it is done.',
  waitingHere: 'This photo is waiting in line. It will appear here when it is done.',

  result: 'Result',
  similarity: 'Similarity',
  regions: 'Regions',
  gradients: 'Gradients',
  outlines: 'Outline shapes',
  size: 'SVG size',
  time: 'Time',
  measuring: 'measuring…',
  export: 'Save',
  saveSvg: 'Save SVG',
  saveAll: 'Save all ({n})',
  copySvg: 'Copy SVG code',
  copied: 'Copied',

  t_added: '{n} photo(s) added. Choose which ones to process.',
  t_queued: '{n} photo(s) are in line. You can keep working.',
  t_allDone: 'All done — {n} photo(s) ready to save.',
  t_removed: '“{name}” removed.',
  t_stopped: 'Stopped {n} photo(s).',
  t_saved: 'Saved.',
  t_savedAll: '{n} SVG file(s) saved.',
  undo: 'Undo',
  close: 'Close',
  err_tooLarge: '“{name}” is too big. Use a photo under 50 MB and at most 8000 px wide.',
  err_notImage: '“{name}” is not a PNG, WebP or JPEG photo.',
  err_full: 'The workbench is full (100 photos). Process or remove some first.',
  err_offline: "Can't reach the converter. Close the app and open it again.",
  err_generic: 'Something went wrong{name}. Please try again. ({detail})',

  confirmStopTitle: 'Stop all photos?',
  confirmStopBody: 'Photos waiting in line are taken out. Finished results stay.',
  keepGoing: 'Keep going',

  tour_skip: 'Skip',
  tour_next: 'Next',
  tour_back: 'Back',
  tour_done: "Let's start",
  tour_step: '{n} of {m}',
  tour1_title: 'Welcome!',
  tour1_body: 'Turn pictures into clean, editable SVG files. Everything happens on this computer. Here is a quick tour.',
  tour2_title: '1 · Add photos',
  tour2_body: 'Drag photos anywhere into this window or press Choose photos. Add as many as you like — nothing is processed yet.',
  tour3_title: '2 · Choose & set up',
  tour3_body: 'Tick the photos you want, then pick a style: Cartoon for drawings, Logo for flat graphics, and so on.',
  tour4_title: '3 · Process',
  tour4_body: 'Photos wait in line and are converted one after another, so your computer stays responsive. Change the speed here.',
  tour5_title: '4 · Compare & save',
  tour5_body: 'Slide between the original and the SVG, zoom in, then save one or all results. You can open this guide again from Guide.',
};

type Dict = typeof en;

const id: Dict = {
  appName: 'PNG to SVG Vectorize',
  tagline: 'Ilustrasi raster menjadi SVG yang rapi dan bisa diedit. Semua tetap di komputer ini.',
  privacy: 'Jalan tanpa internet · foto tidak pernah keluar dari komputer ini',
  language: 'Bahasa',
  help: 'Panduan',
  noToken: 'Halaman ini perlu tautan yang dicetak oleh "png2svg serve" (berisi kunci sesi). Buka tautan itu lagi.',

  step_add: 'Tambah foto',
  step_pick: 'Pilih & atur',
  step_queue: 'Proses',
  step_save: 'Bandingkan & simpan',

  addTitle: 'Tambahkan foto untuk mulai',
  addBody: 'Seret gambar ke sini atau pilih dari komputer. Boleh banyak sekaligus — belum ada yang diproses sampai Anda menekan Proses.',
  addButton: 'Pilih foto',
  addMore: 'Tambah lagi',
  formats: 'PNG, WebP, atau JPEG · maks. 50 MB per foto',
  drop: 'Lepas untuk menambahkan foto ini',

  workbench: 'Meja kerja',
  pickTitle: 'Pilih foto yang mau diproses',
  pickHint: 'Hapus centang pada foto yang mau ditunda dulu.',
  selectAll: 'Pilih semua',
  selectNone: 'Kosongkan',
  selectedCount: '{n} dari {m} dipilih',
  processOne: 'Proses 1 foto',
  processMany: 'Proses {n} foto',
  processNone: 'Pilih foto untuk diproses',
  removeFromBench: 'Keluarkan dari meja kerja',
  benchEmpty: 'Meja kerja masih kosong.',

  queueTitle: 'Sedang diproses',
  waitingPos: 'Menunggu · urutan ke-{n}',
  stopAll: 'Hentikan semua',
  resultsTitle: 'Hasil',
  status_staged: 'Siap',
  status_queued: 'Menunggu',
  status_running: 'Diproses',
  status_done: 'Selesai',
  status_error: 'Gagal diubah',
  status_cancelled: 'Dihentikan',
  stage_start: 'memulai',
  stage_ink: 'membaca garis',
  stage_regions: 'membagi warna',
  stage_curves: 'menghaluskan kurva',
  stage_svg: 'menyusun SVG',
  cancel: 'Hentikan',
  retry: 'Proses lagi',
  remove: 'Hapus',
  failedHelp: 'Foto ini belum berhasil diubah. Coba gaya lain atau proses lagi.',

  speed: 'Kecepatan proses',
  speed_auto: 'Otomatis',
  speed_saver: 'Hemat',
  speed_balanced: 'Seimbang',
  speed_fast: 'Cepat',
  speedHelp_auto: 'Dipilihkan untuk komputer ini: {mode} ({n} foto sekaligus).',
  speedHelp_saver: 'Satu foto sekaligus dengan prioritas rendah — komputer tetap lancar dipakai.',
  speedHelp_balanced: 'Dua foto sekaligus di komputer yang mampu ({n} di sini).',
  speedHelp_fast: 'Hingga {n} foto sekaligus. Paling cocok saat komputer tidak dipakai untuk hal lain.',

  style: 'Gaya hasil',
  styleNote: 'Dipakai untuk foto yang diproses berikutnya.',
  preset_cartoon: 'Kartun',
  preset_flat: 'Ilustrasi datar',
  preset_logo: 'Logo / ikon',
  preset_poster: 'Foto → poster',
  desc_cartoon: 'Gambar dengan garis tinta gelap',
  desc_flat: 'Warna datar tanpa garis',
  desc_logo: 'Sedikit warna, tepi tajam',
  desc_poster: 'Foto menjadi poster sederhana',
  advanced: 'Atur lebih detail',
  opt_outlines: 'Pisahkan garis tinta',
  opt_gradients: 'Isian gradien',
  opt_radial: 'Gradien radial',
  opt_tolerance: 'Toleransi kurva (px)',
  opt_smooth: 'Penghalusan (px)',
  opt_merge_de: 'Gabung warna mirip (ΔE)',
  opt_scale: 'Detail garis (pembesaran)',
  auto: 'otomatis',
  resetPreset: 'Kembalikan ke bawaan gaya',
  reprocess: 'Proses ulang dengan gaya ini',

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
  selectHint: 'Pilih foto yang sudah selesai di sebelah kiri untuk dibandingkan. Gulir untuk zoom, seret untuk geser.',
  notReady: 'SVG muncul di sini setelah selesai.',
  waitingHere: 'Foto ini sedang mengantre. Hasilnya muncul di sini setelah selesai.',

  result: 'Hasil',
  similarity: 'Kemiripan',
  regions: 'Wilayah',
  gradients: 'Gradien',
  outlines: 'Bentuk garis',
  size: 'Ukuran SVG',
  time: 'Waktu',
  measuring: 'mengukur…',
  export: 'Simpan',
  saveSvg: 'Simpan SVG',
  saveAll: 'Simpan semua ({n})',
  copySvg: 'Salin kode SVG',
  copied: 'Tersalin',

  t_added: '{n} foto ditambahkan. Pilih mana yang mau diproses.',
  t_queued: '{n} foto masuk antrean. Anda bisa lanjut bekerja.',
  t_allDone: 'Selesai — {n} foto siap disimpan.',
  t_removed: '“{name}” dihapus.',
  t_stopped: '{n} foto dihentikan.',
  t_saved: 'Tersimpan.',
  t_savedAll: '{n} berkas SVG tersimpan.',
  undo: 'Urungkan',
  close: 'Tutup',
  err_tooLarge: '“{name}” terlalu besar. Pakai foto di bawah 50 MB dan lebar maks. 8000 px.',
  err_notImage: '“{name}” bukan foto PNG, WebP, atau JPEG.',
  err_full: 'Meja kerja penuh (100 foto). Proses atau keluarkan sebagian dulu.',
  err_offline: 'Mesin pengubah tidak bisa dihubungi. Tutup aplikasi lalu buka lagi.',
  err_generic: 'Ada yang tidak beres{name}. Silakan coba lagi. ({detail})',

  confirmStopTitle: 'Hentikan semua foto?',
  confirmStopBody: 'Foto yang masih mengantre dikeluarkan dari antrean. Hasil yang sudah selesai tetap ada.',
  keepGoing: 'Lanjutkan',

  tour_skip: 'Lewati',
  tour_next: 'Lanjut',
  tour_back: 'Kembali',
  tour_done: 'Ayo mulai',
  tour_step: '{n} dari {m}',
  tour1_title: 'Selamat datang!',
  tour1_body: 'Ubah gambar menjadi berkas SVG yang rapi dan bisa diedit. Semua terjadi di komputer ini. Berikut tur singkatnya.',
  tour2_title: '1 · Tambah foto',
  tour2_body: 'Seret foto ke mana saja di jendela ini atau tekan Pilih foto. Tambahkan sebanyak yang Anda mau — belum ada yang diproses.',
  tour3_title: '2 · Pilih & atur',
  tour3_body: 'Centang foto yang mau diproses, lalu pilih gaya: Kartun untuk gambar bergaris, Logo untuk grafis datar, dan seterusnya.',
  tour4_title: '3 · Proses',
  tour4_body: 'Foto mengantre dan diubah satu per satu sehingga komputer tetap lancar. Kecepatannya bisa diatur di sini.',
  tour5_title: '4 · Bandingkan & simpan',
  tour5_body: 'Geser untuk membandingkan asli dan SVG, perbesar, lalu simpan satu atau semua hasil. Panduan ini bisa dibuka lagi lewat tombol Panduan.',
};

export type Lang = 'en' | 'id';
export type Key = keyof Dict;
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

export function t(key: Key): string {
  return dicts[i18n.lang][key];
}

/** Lookup by a computed key (status_*, stage_*, preset_*); unknown keys fall back to the key itself. */
export function tk(key: string): string {
  return (dicts[i18n.lang] as Record<string, string>)[key] ?? key;
}

/** Text with {placeholders}. */
export function tf(key: Key, vars: Record<string, string | number>): string {
  return t(key).replace(/\{(\w+)\}/g, (_, k: string) => String(vars[k] ?? ''));
}
