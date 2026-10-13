# Rencana PNG to SVG Vectorize — menuju v1.0 (aplikasi desktop Windows & macOS)

> Status: disusun 2026-10-12. Kondisi awal = v0.1: mesin vektorisasi (Python) + CLI `png2svg` + 5 tes,
> dipindahkan dari monorepo Turion (`tools/vectorize`). Target v1.0: **aplikasi desktop terpasang di Windows 10/11
> dan macOS 12+**, mesin dengan kualitas kurva & ukuran file mendekati tools berbayar, dan arsitektur yang sama
> bisa dijalankan sebagai **web app** di versi berikutnya.

---

## 1. Tujuan & ukuran keberhasilan v1.0

| Target | Ukuran |
|---|---|
| Kualitas visual | Kemiripan render ≥ 98% (MAE) pada set uji kartun; tidak ada cacat terlihat di perbesaran 2× (checklist §8) |
| Kerapian kurva | Jumlah segmen path turun ≥ 50% dibanding v0.1 pada set uji, tanpa turun kemiripan > 0,3 poin |
| Ukuran file | Median ukuran SVG turun ≥ 40% dibanding v0.1 |
| Kecepatan | ≤ 8 detik untuk gambar 1536×1024 di laptop 4 core (v0.1: 15–25 detik) |
| Aplikasi | Installer Windows (`.exe`, x64) dan macOS (`.dmg`, Apple Silicon + Intel); buka → seret gambar → lihat perbandingan → simpan SVG, tanpa terminal |
| Privasi | Semua proses lokal; tidak ada unggahan, tidak ada telemetri |

Di luar cakupan v1.0: editor vektor (mengedit node), akun/cloud, mobile app, vektorisasi foto realistis tingkat tinggi.

## 2. Arsitektur

```text
┌──────────────────────── aplikasi desktop (satu proses Python) ─────────────────────────┐
│  pywebview window  ──HTTP 127.0.0.1:<port acak> + token──►  FastAPI (service lokal)    │
│  (WebView2 / WKWebView)                                        │                       │
│        ▲                                                       ▼                       │
│   UI Svelte (file statis hasil build)              pngsvg (mesin, pustaka Python)       │
└────────────────────────────────────────────────────────────────────────────────────────┘
Web app (versi berikutnya) = FastAPI yang sama di server + UI yang sama di browser.
```

| Lapisan | Folder | Teknologi | Tanggung jawab |
|---|---|---|---|
| Mesin | `src/pngsvg/` | Python 3.10+, numpy, scipy, Pillow (vtracer dilepas di M2) | PNG → SVG, tanpa I/O jaringan; API `vectorize(image, Options)` |
| Service | `src/pngsvg_app/server.py` | FastAPI + uvicorn | Endpoint: `POST /api/jobs` (unggah + opsi), `GET /api/jobs/{id}` (progres, hasil), `GET /api/jobs/{id}/svg`, `GET /api/presets`; antrean job di thread pool |
| UI | `app/ui/` | Svelte 5 + Vite + TypeScript | Seret-lepas, antrean, pratinjau, pengaturan, ekspor |
| Shell desktop | `src/pngsvg_app/desktop.py` | pywebview | Jendela native, dialog buka/simpan file native, menjalankan service |
| Paket | `packaging/` | PyInstaller, Inno Setup (Win), `hdiutil`/create-dmg (mac) | Installer per OS lewat GitHub Actions |

### Alasan pilihan (dan alternatif yang ditolak)
- **pywebview + FastAPI + Svelte**: satu bahasa backend (mesin sudah Python), UI web modern yang **sama** untuk desktop
  dan web, installer kecil karena memakai webview bawaan OS (WebView2 sudah ada di Windows 10/11, WKWebView di macOS).
- Ditolak: **Electron** (bundel Chromium ±150 MB + tetap butuh Python), **Tauri** (perlu Rust + sidecar Python → dua
  toolchain), **Qt/PySide** (UI tidak bisa dipakai ulang untuk web), **Flet/NiceGUI** (kontrol UI kurang fleksibel untuk
  pratinjau berdampingan dengan zoom sinkron).

### Keamanan service lokal
- Hanya `bind 127.0.0.1`, port acak, **token acak per sesi** wajib di header setiap request (mencegah situs lain di
  browser memanggil API lokal).
- Batas ukuran unggahan (mis. 50 MB) dan dimensi (mis. 8000 px sisi panjang); validasi format dengan Pillow
  (bukan dari ekstensi); `Image.MAX_IMAGE_PIXELS` dibatasi untuk mencegah *decompression bomb*.
- Tidak ada telemetri, tidak ada request keluar.

## 3. Peningkatan mesin (engine)

| ID | Pekerjaan | Hasil yang diharapkan |
|---|---|---|
| E1 | **Fitting kurva sendiri** (algoritma Schneider: Bezier kubik dengan toleransi galat, deteksi sudut dari sudut belok) menggantikan spline pendek vtracer; vtracer hanya untuk kontur mentah (atau ganti dengan marching squares sendiri) | Segmen −50% atau lebih, kurva lebih mulus, sudut tajam tetap tajam — ✅ M2 (`curves.py`; toleransi per titik, longgar di bawah outline) |
| E2 | **Peta batas bersama (planar map)**: label wilayah → graf batas; setiap batas antar dua wilayah dilacak & di-fit sekali, dipakai kedua wilayah (tanpa tumpang-tindih 2 px) | File −30–50%, tanpa celah/seam, tepi antar-warna konsisten — ✅ M2 (`planar.py`; vtracer tidak dipakai lagi) |
| E3 | **Radial gradient**: deteksi wilayah berbentuk blob dengan pusat terang/gelap (rona pipi, bola) → `radialGradient` | Rona pipi & highlight bulat lebih mirip — ✅ M3 (`gradients.py`: fit kerucut elips; pertumbuhan radial menyatukan pita konsentris; stop least-squares) |
| E4 | **Paralel**: fitting/tracing per wilayah di `ProcessPoolExecutor`; profil & optimasi titik panas (bincount, label) | ≤ 8 detik per gambar 1536×1024 — ✅ M3 untuk median (7,2 s, pool 4 proses); terberat 9,8 s. Paralel lewat `executor=` (pustaka) / `--jobs` (CLI): banyak file = satu file per proses; satu file = fitting kurva paralel |
| E5 | **Preset**: `cartoon` (bawaan), `flat-illustration`, `logo/icon` (warna datar, sedikit wilayah), `poster` (foto → gaya poster) | Hasil baik tanpa mengatur parameter — ✅ M3 (`presets.py`, `--preset`; angka di `docs/bench.md`) |
| E6 | **Kemiripan tanpa Chrome**: di aplikasi, SVG dirender oleh webview ke `<canvas>` lalu dibandingkan dengan PNG (JS) | Skor kualitas langsung di UI — ✅ M4 (`app/ui/src/lib/similarity.ts`) |
| E7 | **Set uji pembanding** (`bench/`): 20–30 gambar berlisensi bebas (kartun, logo, ikon, flat, poster) + skrip yang mencatat kemiripan/ukuran/segmen/waktu ke tabel; perbandingan manual dengan Vectorizer.ai/Illustrator di beberapa gambar | Klaim kualitas berbasis angka; regresi terdeteksi di CI — ✅ M6 (27 gambar CC0/PD Commons, manifest + sha256, job CI `bench`; perbandingan manual: `docs/compare-tools.md`) |

## 4. Fitur aplikasi v1.0

- **Seret-lepas** satu atau banyak gambar (PNG, WebP, JPEG) atau tombol "Buka".
- **Antrean** dengan progres per file, batal, ulangi.
- **Pratinjau berdampingan** PNG ↔ SVG dengan zoom & geser tersinkron (hingga 800%), plus mode **slider** (geser
  pembatas di atas satu gambar); tampilan lapisan (isian saja / garis saja).
- **Pengaturan**: preset (§E5) + panel lanjutan (detail, garis on/off, gradien on/off, skala) dengan pratinjau ulang.
- **Info hasil**: skor kemiripan, jumlah wilayah/gradien/path, ukuran file, waktu proses.
- **Ekspor**: simpan SVG (dialog native), simpan semua ke folder, salin kode SVG ke clipboard.
- Tema terang/gelap mengikuti OS; bahasa **Inggris & Indonesia**.
- Ingat pengaturan terakhir (lokal).

## 5. Distribusi

| OS | Artefak | Catatan |
|---|---|---|
| Windows 10/11 x64 | `PNG-to-SVG-Vectorize-Setup-x.y.z.exe` (Inno Setup) + `.zip` portable | WebView2 runtime sudah ada di Win 10/11; installer memeriksa & menautkan unduhannya bila tidak ada |
| macOS 12+ | `PNG-to-SVG-Vectorize-x.y.z-arm64.dmg` dan `-x64.dmg` | Dibangun di runner `macos-14` (arm64) dan runner Intel |

- Build otomatis saat tag `v*` di GitHub Actions → GitHub Releases.
- **Penandatanganan kode (keputusan pemilik, §9):** tanpa sertifikat, Windows menampilkan peringatan SmartScreen dan
  macOS memblokir aplikasi sampai pengguna mengizinkan lewat System Settings. v1.0 bisa rilis tanpa tanda tangan dengan
  panduan instalasi; penandatanganan + notarization disarankan sebelum promosi luas.

## 6. Struktur repo (target v1.0)

```text
png-to-svg-vectorize/
  src/pngsvg/            mesin + CLI png2svg
  src/pngsvg_app/        server.py (FastAPI), desktop.py (pywebview), static/ (UI hasil build)
  app/ui/                sumber UI Svelte + Vite
  bench/                 gambar uji + skrip pembanding
  packaging/             pyinstaller.spec, windows/installer.iss, macos/ (ikon, Info.plist, dmg)
  tests/                 tes mesin, tes API (httpx), tes UI e2e (Playwright, mode web)
  docs/                  PLAN.md, arsitektur, panduan pengguna (EN/ID)
  .github/workflows/     ci.yml (tes 3 OS), release.yml (installer Win/mac)
```

## 7. Tahapan (milestone)

| Tahap | Isi | Selesai bila |
|---|---|---|
| **M0** — Fondasi repo (✅ dimulai 2026-10-12) | Pindah kode ke `src/pngsvg`, CLI `png2svg`, README, lisensi MIT, CI tes Windows/macOS/Linux | CI hijau di 3 OS |
| **M1** — Set uji & baseline (✅ 2026-10-12) | `bench/` + skrip; catat angka v0.1 (kemiripan, ukuran, segmen, waktu) | Tabel baseline di `docs/bench.md` |
| **M2** — Mesin kualitas (E1, E2) (✅ 2026-10-12, v0.2) | Fitting kurva Schneider + planar map | Target segmen −50%, ukuran −40%, kemiripan tidak turun > 0,3 — tercapai: set Turion segmen −69%, ukuran −58%, kemiripan +0,08 (lihat `docs/bench.md`) |
| **M3** — Mesin lanjutan (E3, E4, E5) (✅ 2026-10-12, v0.3) | Radial gradient, paralel, preset; bonus: tepi sub-piksel, deteksi tinta adaptif | ≤ 8 detik/gambar; preset logo/ikon bagus di set uji — tercapai (median 7,2 s; preset `logo` sama/lebih baik dari `cartoon` di 4 gambar logo/ikon, jumlah wilayah tepat) |
| **M4** — Service + UI (web mode) (✅ 2026-10-12, v0.4) | FastAPI + UI Svelte lengkap §4, jalan di browser lokal (`png2svg serve`); E6 skor kemiripan di UI (canvas) | Tes API + tes e2e Playwright hijau |
| **M5** — Desktop & paket (✅ 2026-10-12, v0.5) | pywebview, dialog native, PyInstaller, installer Win/mac, `release.yml` | Installer terpasang & berjalan di Windows 11 dan macOS (arm64 + Intel), tes asap di CI — build + tes asap hijau di CI (Win x64, mac arm64, mac Intel `macos-15-intel`); exe lokal Windows terbuka & melayani UI; uji pasang di perangkat nyata masuk checklist M6 |
| **M6** — Rilis v1.0 (✅ dokumen & set uji 2026-10-12; tag menunggu persetujuan pemilik) | Panduan pengguna EN/ID, tangkapan layar, catatan rilis, set uji E7, checklist visual; tanpa tanda tangan kode (P-1) | Tag `v1.0.0`, artefak di GitHub Releases |
| **M7** — UX v1.1 (✅ 2026-10-13, v1.1.0; tag menunggu persetujuan pemilik) | Lihat §7a: alur bertahap (tambah → pilih & atur → antrean → bandingkan & simpan), antrean hemat sumber daya, komponen UI kustom + micro-interaction, tutorial pertama kali | Tes API + e2e hijau, installer v1.1.0 terpasang lokal untuk QA pemilik |

Setiap tahap: tes otomatis hijau, angka `bench/` dicatat (tidak boleh turun tanpa alasan), dokumen diperbarui.

### 7a. M7 — UX v1.1 (permintaan pemilik 2026-10-13)

Masalah v1.0: foto langsung diproses begitu dipilih; 4 gambar diproses bersamaan sehingga laptop lemah terasa berat;
kontrol masih bawaan browser/OS (select, checkbox, range); tidak ada panduan bagi pengguna non-teknis.

**Alur baru (bahasa manusia, satu tombol utama per langkah)**
1. **Tambah foto** — seret, tempel, atau tombol "Pilih foto" (banyak sekaligus). Foto divalidasi saat itu juga
   (format, ukuran ≤ 50 MB, sisi ≤ 8000 px) dan masuk **meja kerja** sebagai status `staged` — belum diproses.
   Penolakan dijelaskan per foto dengan bahasa awam ("Foto ini terlalu besar…").
2. **Pilih & atur** — kartu thumbnail dengan checkbox (semua tercentang default), "Pilih semua / Kosongkan",
   jumlah terpilih; gaya hasil sebagai kartu visual (Kartun, Logo, Ikon, Foto datar, …) + pengaturan lanjutan
   tersembunyi (progressive disclosure). Tombol utama: **"Proses N foto"**.
3. **Antrean** — foto masuk antrean FIFO; tampil posisi ("Menunggu · urutan 2"), tahap dalam bahasa awam
   (membaca garis → membagi warna → menghaluskan kurva → menyusun SVG), batal per foto / batalkan semua.
4. **Bandingkan & simpan** — tampilan geser/berdampingan yang sudah ada, skor kemiripan, simpan satu/semua.

**Antrean hemat sumber daya (server)**
- `JobManager` jadi antrean sungguhan: dispatcher hanya mengirim *n* job berjalan sekaligus (*n* = kecepatan),
  sisanya menunggu di antrean (bisa dibatalkan seketika, tidak memakan memori pekerja).
- Kecepatan: **Hemat** (1), **Seimbang** (2 bila ≥ 4 core), **Cepat** (≤ min(4, core − 1)); default **Otomatis**
  (keputusan pemilik): dipilih dari jumlah core & RAM saat aplikasi dibuka. Bisa diganti kapan saja (`PUT /api/settings`).
- Proses pekerja berprioritas rendah (Windows `BELOW_NORMAL_PRIORITY_CLASS`, POSIX `nice`) agar laptop tetap lancar.
- Batas meja kerja (mis. 100 foto) dengan pesan yang jelas.

**Komponen UI kustom (tanpa kontrol native)**: tombol (primer/sekunder/hantu/bahaya + loading + efek tekan), checkbox,
switch, segmented control, dropdown/listbox (bahasa, gaya), slider dengan nilai, toast bertumpuk (ikon, auto-tutup,
"Urungkan"), dialog (focus trap), progress ring, skeleton, empty state berilustrasi, scrollbar kustom, tooltip.
Micro-interaction 150–300 ms (hover, tekan, drop zone berdenyut, centang tergambar saat selesai, angka naik),
semuanya menghormati `prefers-reduced-motion`; fokus keyboard terlihat; WCAG AA.

**Tutorial pertama kali**: 4–5 langkah coach-mark dengan sorotan pada elemen nyata (tambah foto → pilih → proses →
bandingkan → simpan), tombol Lewati/Kembali/Lanjut, titik progres, Esc = lewati; disimpan di `localStorage`;
bisa diulang dari tombol "Panduan" di header.

**Pengerasan (hardening)**: semua aksi menampilkan status (memuat/sukses/gagal) dengan pesan awam + tindakan;
tombol dinonaktifkan selama aksi berjalan (anti klik ganda); hapus hasil bisa diurungkan; peringatan saat menutup
jendela ketika masih ada foto diproses; batas & validasi tetap di server.

**Verifikasi**: pytest (staged → start, antrean membatasi job berjalan, posisi, batal di antrean, kecepatan, batas
meja kerja), Playwright (alur penuh: tambah banyak → pilih sebagian → proses → selesai; tutorial lewati/selesai;
kecepatan), `svelte-check`, build installer v1.1.0 + tes asap, pasang lokal.

## 8. Pengujian

- **Mesin:** unit test (round-trip path, SVG murni, mode datar, kemiripan render), tes properti untuk fitting kurva
  (galat maksimum ≤ toleransi), tes regresi `bench/` (kemiripan/ukuran per gambar dibanding baseline ± ambang).
- **Service:** httpx + pytest: token wajib, batas ukuran, format ditolak, alur job lengkap.
- **UI:** Playwright terhadap mode web (seret-lepas, antrean, ekspor).
- **Paket:** tes asap di CI (aplikasi terbangun, proses jalan, endpoint kesehatan menjawab, lalu ditutup).
- **Checklist visual** per rilis: garis tidak bergerigi, tidak ada celah antar-wilayah, gradien tanpa pita, mulut/mata
  utuh, rona pipi tetap, tidak ada pinggiran terang — diperiksa di perbesaran 2×.

## 9. Keputusan yang dibutuhkan dari pemilik

| # | Pertanyaan | Opsi | Rekomendasi |
|---|---|---|---|
| P-1 | Penandatanganan kode | — | ✅ **Diputuskan 2026-10-12: tanpa tanda tangan** (gratis, open source). Panduan instalasi menjelaskan peringatan SmartScreen/Gatekeeper dan cara membuka |
| P-2 | Nama & ikon aplikasi | — | ✅ Nama "PNG to SVG Vectorize"; logo `assets/logo.svg` (+ `logo-small.svg` untuk 16–48 px), ikon `.ico`/`.icns`/PNG lewat `scripts/build_icons.py` |
| P-3 | Rilis ke PyPI | Ya / nanti | **Ya** setelah M2 (nama distribusi `png-to-svg-vectorize`) |
| P-4 | Versi web publik (di-hosting) | Tidak di v1.0 / ya | **Tidak di v1.0**: arsitektur sudah siap, hosting menambah biaya & isu privasi unggahan |

## 10. Risiko

| Risiko | Mitigasi |
|---|---|
| PyInstaller + numpy/scipy menghasilkan bundel besar (±150–250 MB) | Mode `onedir` + UPX selektif, buang modul scipy yang tak dipakai; ukur di M5 |
| Antivirus/SmartScreen menandai exe PyInstaller tanpa tanda tangan | Dokumentasi; tanda tangan kode (P-1) |
| Runner GitHub macOS Intel makin terbatas | Bangun `x64` di runner Intel selama tersedia; alternatif universal2 lewat Python universal |
| Fitting kurva baru menurunkan kemiripan | Toleransi galat terukur + regresi `bench/` di CI |
| Gambar besar menghabiskan memori | Batas dimensi, pemrosesan per wilayah, `onedir` |

---

## Ringkas (English)

Path to v1.0: engine quality (custom Schneider curve fitting, shared-boundary planar map, radial gradients,
parallelism, presets, benchmark suite), then a local FastAPI service + Svelte UI usable in the browser, wrapped by
pywebview into native Windows/macOS apps built with PyInstaller in GitHub Actions. Everything runs locally; no uploads.
