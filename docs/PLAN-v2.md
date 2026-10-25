# Rencana v2 — PNG to SVG Vectorize: lengkap seperti aplikasi berbayar, tetap gratis

> Status: **draf rencana**, 2026-10-13. Lanjutan dari [PLAN.md](PLAN.md) (M0–M7 selesai, v1.1.0).
> Keputusan pemilik (2026-10-13): tiga tema visual sebagai pilihan bebas; urutan **M8 → M9 (AI) → M10**; model AI
> **diunduh opsional**; **tetap open source tanpa tanda tangan kode berbayar**. "Enterprise" di sini berarti
> **fitur selengkap aplikasi vektorisasi komersial, dengan kelebihan: gratis, offline, privat, dan open source**.
> Ditambah rencana **website produk** (M11).

---

## 1. Posisi produk

| | Kita | Aplikasi lain (gambaran umum, perlu dicek ulang saat menulis halaman Bandingkan) |
|---|---|---|
| Harga | Gratis, open source (MIT) | Langganan / bayar per gambar / bagian dari paket desain berbayar |
| Privasi | Semua di komputer sendiri, tanpa unggah | Banyak yang memproses di server |
| Kualitas | Gradien linear + radial, garis tinta terpisah, skor kemiripan terukur | Bervariasi; jarang menampilkan angka kemiripan |
| Massal | Antrean + (M10) folder pantau, profil, laporan | Sering terbatas di paket mahal |

Kalimat utama: **"Vektorisasi kelas studio. Gratis, offline, dan terbuka."**

Prinsip yang dijaga di setiap milestone: tetap offline secara bawaan (jaringan hanya untuk unduhan yang diminta
pengguna), angka kualitas dibuktikan dengan `bench/`, dan setiap fitur baru punya tes otomatis.

---

## 2. M8 — Identitas visual & Pengaturan (v1.2) — ✅ 2026-10-18

### 2.1 Tema (tiga pilihan bebas)

Tema lahir dari tujuan aplikasi — **meja gambar & pena** (raster → garis vektor yang presisi). Prinsip dari kosakata
sinematografi/material yang diterjemahkan ke UI:

| Prinsip | Penerapan |
|---|---|
| Pencahayaan (chiaroscuro) | Kanvas/gambar adalah bagian paling "terang"; bingkai UI mundur dan tenang |
| Material (matte, kertas, tinta) | Permukaan matte, grid halus seperti cutting mat, garis 1 px tegas; tanpa glossy/glassmorphism/glow |
| Suasana (serene, crafted) | Studio ilustrator, bukan dasbor SaaS |
| Komposisi (leading lines) | Alur kiri → tengah → kanan = langkah 1–4; motif **titik node bezier** sebagai aksen (checkbox, progress, kursor, ikon) |
| Warna (earthy/desaturated + 1 aksen bermakna) | Netral hangat + satu aksen per tema; warna status (sukses/gagal) tetap semantik |

| Tema | Mode | Netral | Aksen | Rasa |
|---|---|---|---|---|
| **Kertas & tinta** | terang | kertas `#F3EEE4`, panel `#FBF8F1`, tinta `#1F1B16` | merah pena koreksi `#D9472B`, biru kobalt `#2B4C9A` (garis vektor) | earthy, tenang |
| **Lightbox** | gelap | grafit `#141312` / `#24211E`, teks `#EDE6DA` | amber lampu meja `#F2A33A` | chiaroscuro, grading sinematik desaturasi |
| **Cetak biru** | gelap | biru `#12324F` / `#173E62`, teks `#E6EEF7` | kuning plotter `#F4C95D` | teknik, presisi |

- Default: **ikut sistem** (terang → Kertas & tinta, gelap → Lightbox); pengguna bebas memilih ketiganya.
- Semua warna lewat token CSS per tema (`[data-theme]`), **tes kontras otomatis** (WCAG AA 4,5:1 teks, 3:1 komponen)
  untuk setiap tema — gagal = CI merah.
- Font dibundel (lisensi OFL): sans humanis untuk UI + mono untuk angka (ukuran, %, waktu). Hapus ketergantungan pada
  font sistem agar tampilan sama di Windows dan macOS.
- Ikon menu/aplikasi & ilustrasi kosong disesuaikan dengan motif pena/node.

### 2.2 Halaman Pengaturan

Dibuka dari ikon roda gigi di header (juga `Ctrl+,`). Semua tersimpan lokal; bagian pemrosesan disimpan di service.

| Kelompok | Isi |
|---|---|
| Tampilan | Bahasa · Tema (Sistem / Kertas & tinta / Lightbox / Cetak biru) · Kepadatan (nyaman/ringkas) · Ukuran teks · Kurangi animasi (ikut sistem / selalu / tidak) · Tampilkan ulang panduan |
| Pemrosesan | Kecepatan (Otomatis/Hemat/Seimbang/Cepat, sudah ada) · batas memori per foto · batas foto di meja kerja · (M9) akselerasi AI: Otomatis / GPU / CPU saja |
| Hasil | Gaya bawaan · folder simpan bawaan · pola nama berkas (`{nama}`, `{gaya}`, `{tanggal}`) · presisi koordinat (0–3 desimal) · `width/height` + `viewBox` atau `viewBox` saja · minify · awalan ID |
| Privasi & data | Hapus semua hasil saat aplikasi ditutup · log diagnostik (aktif/mati, buka folder log) |
| Tentang | Versi, lisensi pihak ketiga, tautan repo & panduan; **cek pembaruan opsional** (mati secara bawaan) |

### 2.3 i18n berbasis berkas

- Kamus pindah dari kode ke `locales/<kode>.json` (en, id) + skema kunci; bahasa baru = tambah satu berkas.
- Tes: semua bahasa punya kunci yang sama, placeholder `{n}` cocok, tidak ada teks hardcode di komponen.
- Panduan kontribusi terjemahan di `CONTRIBUTING.md`.

**Realisasi (2026-10-18, v1.2.0)** — semua butir di atas terpasang, dengan penyesuaian:
- *Minify* tidak dijadikan opsi: SVG dari mesin sudah tanpa spasi berlebih dan memakai sintaks angka terpendek.
- *Awalan ID* tidak dijadikan opsi: ID gradien tetap otomatis unik per foto (aman disisipkan banyak SVG di satu halaman).
- *Hapus hasil saat ditutup* tidak perlu disetel: hasil memang hanya ada di memori, jadi ditampilkan sebagai keterangan.
- *Kurangi animasi* punya dua pilihan (ikuti sistem / kurangi); "jangan pernah kurangi" sengaja tidak ada agar setelan
  aksesibilitas sistem tetap dihormati.
- Selain uji kontras, `npm run check` juga menolak warna literal di komponen (semua warna wajib lewat token tema).

**Selesai bila**: tiga tema lolos tes kontras & tes e2e visual; Pengaturan lengkap dengan e2e per kelompok; opsi hasil
berpengaruh nyata ke SVG (tes API); versi 1.2.0.

---

## 3. M9 — AI pra-proses (v1.3) — ✅ 2026-10-25

Tujuan: hasil semulus PNG sumber, terutama untuk gambar kecil, buram, atau JPEG berartefak.

- **Alur**: gambar → (opsional) model AI *upscale + denoise* → mesin vektorisasi yang sudah ada. Mesin tidak diganti.
- **Runtime**: ONNX Runtime — Windows: DirectML (GPU apa pun) → CPU; macOS: CoreML → CPU. Pilihan di Pengaturan:
  Otomatis / GPU / CPU saja, beserta deteksi perangkat dan uji singkat.
- **Model**: kandidat keluarga Real-ESRGAN (umum & varian anime/ilustrasi). Sebelum dipakai: cek lisensi model &
  bobot, ukuran, dan kualitas di set uji. Diunduh **sekali, atas persetujuan pengguna**, dari rilis GitHub repo ini
  (bukan pihak ketiga), diverifikasi SHA-256, disimpan di folder data pengguna; setelah itu offline.
- **UI**: sakelar "Perhalus dengan AI" per gaya (bawaan aktif untuk JPEG/gambar < 800 px), perkiraan waktu, tampilan
  bandingkan Asli / Setelah AI / SVG.
- **Bukti**: tambah kolom bench "dengan AI"; target kemiripan +0,3 poin dan segmen −20 % pada gambar kecil/berartefak,
  tanpa regresi di gambar bersih. Kalau target tidak tercapai, fitur tetap opsional dan diberi label eksperimental.
- **Eksperimen lanjutan (bukan target v1.3)**: segmentasi berbasis model untuk batas wilayah; dicatat hasilnya di
  `docs/bench.md`.

**Selesai bila**: unduh model + verifikasi + GPU/CPU fallback teruji (termasuk tanpa GPU), bench sebelum/sesudah
dicatat, e2e alur AI, versi 1.3.0.

**Realisasi (2026-10-25, v1.3.0)**:
- Model: Real-ESRGAN `RealESRGAN_x4plus_anime_6B` → **Ilustrasi** (17 MB, bawaan) dan `realesr-general-x4v3` →
  **Umum** (5 MB); bobot resmi BSD-3-Clause dikonversi ke ONNX opset 17 oleh `tools/models/convert.py` (selisih vs
  PyTorch < 1e-6), diunggah ke rilis `models-v1` bersama `manifest.json`, `SHA256SUMS`, dan lisensi upstream.
- Bench pemulihan (10 gambar E7 yang dirusak setengah ukuran + JPEG q60): Ilustrasi **+0,47** poin median (target
  +0,3 tercapai), ukuran +7 %; Umum +0,27, ukuran +60 %. Detail di `docs/bench.md`.
- Penyesuaian: ambang Otomatis **1000 px** (bukan 800) atau JPEG; sakelar global di panel gaya (bukan per gaya);
  hasil AI ditelusuri di 2× ukuran foto dengan presisi koordinat dikurangi satu agar ukuran berkas terkendali.
- Ditunda: perkiraan waktu, tampilan bandingkan "Setelah AI", uji singkat perangkat, dan target −20 % segmen (belum
  diukur). macOS Intel: tidak ada build ONNX Runtime, jadi fitur AI disembunyikan di sana.
- Teruji: unduh + checksum + batal/hapus (pytest dengan server lokal), API & job AI end to end dengan model ONNX mini,
  fallback CPU (`providers_for` selalu diakhiri CPU), e2e UI (kartu model, akselerator, Mati/Otomatis/Selalu, baris
  statistik).

---

## 4. M10 — Fitur lengkap "kelas studio" (v1.4–v1.5)

Daftar diambil dari fitur yang umum ada di aplikasi vektorisasi komersial dan alat tracing populer. Prioritas P1 dulu.

| # | Fitur | Prioritas | Catatan |
|---|---|---|---|
| F1 | **Kontrol palet**: jumlah warna maksimal, kunci/ubah warna palet, gabung warna dari pratinjau | P1 | Paling sering diminta desainer |
| F2 | **Format keluaran**: SVG, PDF, EPS, DXF (CAD/laser), PNG beresolusi tinggi dari vektor | P1 | Konversi dari SVG internal |
| F3 | **Mode tumpuk vs potong** (stacked/cutout) + pengisi celah tipis antarwilayah | P1 | Menghilangkan garis putih tipis saat diperbesar |
| F4 | **Hapus latar / abaikan putih**, latar transparan | P1 | |
| F5 | **Filter bintik** (luas wilayah minimum) | P1 | Sebagian sudah ada lewat penggabungan warna |
| F6 | **Mode hitam-putih & grayscale** (+ ambang) | P1 | Logo, stempel, tanda tangan |
| F7 | **Centerline tracing** (garis tengah) | P2 | Gambar garis, tulisan tangan, plotter/laser |
| F8 | **Edit ringan di aplikasi**: pilih wilayah → ubah warna/hapus/gabung; urungkan/ulangi | P2 | |
| F9 | **Profil gaya** simpan/ekspor/impor (`.pngsvg-profile.json`) | P1 | Konsistensi tim |
| F10 | **Folder pantau** (masuk PNG → keluar SVG) & **CLI dengan profil** | P2 | Otomasi |
| F11 | **Laporan batch** CSV/JSON (kemiripan, ukuran, waktu, gaya) | P2 | QA tim |
| F12 | **Tempel gambar** dari clipboard (`Ctrl+V`), salin SVG/PNG ke clipboard | P1 | |
| F13 | **SVG ramah aplikasi desain**: grup per warna/lapisan, nama lapisan, ID stabil | P2 | Figma, Illustrator, Inkscape |
| F14 | **Riwayat per foto**: bandingkan beberapa percobaan gaya berdampingan | P3 | |
| F15 | **Pintasan keyboard** lengkap + lembar pintasan (`?`) | P2 | |

Distribusi tetap gratis tanpa sertifikat berbayar: installer Windows (Inno Setup) + zip portable + DMG, panduan
SmartScreen/Gatekeeper, checksum SHA-256 di setiap rilis, build dapat direproduksi dari CI publik. Opsional nanti:
paket di winget/Homebrew (gratis), PyPI untuk mesin.

**Selesai bila**: setiap fitur P1 punya tes API + e2e dan dibuktikan di bench (untuk yang memengaruhi kualitas);
halaman Bandingkan di website memakai angka nyata.

---

## 5. M11 — Website produk (product marketing website)

Jenis: **product website / product marketing website** — seperti situs produk Android: memamerkan fitur dan
teknologi, menjelaskan cara kerja, dan mengajak mengunduh. Bukan blog dan bukan aplikasi web.

### 5.1 Tujuan & ukuran
- Pengunjung paham dalam 10 detik: *apa ini, kenapa gratis & aman, seberapa bagus hasilnya*.
- Satu ajakan utama: **Unduh gratis** (Windows / macOS, otomatis mendeteksi OS); ajakan kedua: **Lihat di GitHub**.
- Ukuran: unduhan per rilis (statistik GitHub Releases), bintang repo. **Tanpa pelacak pihak ketiga** (selaras dengan
  pesan privasi); kalau perlu angka kunjungan, pakai analitik tanpa cookie yang di-host sendiri — keputusan pemilik.

### 5.2 Halaman
| Halaman | Isi |
|---|---|
| **Beranda** | Hero dengan **penggeser sebelum/sesudah** interaktif (PNG ↔ SVG, bisa di-zoom untuk membuktikan ketajaman), kalimat utama, tombol unduh; 3 pilar (Kualitas studio · Offline & privat · Gratis & terbuka); cuplikan alur 4 langkah; galeri singkat; FAQ |
| **Fitur** | Per fitur: gradien, garis tinta, antrean hemat sumber daya, AI pra-proses (setelah M9), format keluaran, profil & otomasi; visual nyata dari aplikasi |
| **Cara kerja** | Penjelasan mesin untuk orang awam + versi teknis (planar map, kurva Bezier, gradien) dengan diagram |
| **Galeri** | Contoh dari set uji E7 (CC0/PD) dengan angka kemiripan, ukuran berkas, waktu; filter per jenis gambar |
| **Bandingkan** | Tabel jujur vs alat lain (fitur, harga, privasi), metode perbandingan ditulis terbuka; tanpa klaim yang tidak bisa dibuktikan |
| **Unduh** | Windows / macOS (arm64 & Intel), versi, ukuran, checksum, langkah SmartScreen/Gatekeeper bergambar, persyaratan sistem |
| **Panduan** | Panduan pengguna EN/ID (dari `docs/user-guide.*.md`) |
| **Catatan rilis** | Dari `CHANGELOG.md` |
| **Open source** | Lisensi, cara berkontribusi (kode, terjemahan, contoh gambar), peta jalan |
| **Privasi** | Situs tanpa pelacak; aplikasi offline |

### 5.3 Desain & teknologi
- Memakai **sistem tema yang sama** (Kertas & tinta / Lightbox / Cetak biru) agar situs dan aplikasi satu identitas;
  motif node bezier & garis pena untuk ilustrasi; tangkapan layar asli dari Playwright.
- Situs **statis** (rekomendasi: Astro atau Vite + Svelte yang sudah dipakai UI aplikasi), di-host gratis di
  **GitHub Pages** dari repo yang sama (`site/`), dibangun oleh CI saat rilis; domain: `*.github.io` dulu, domain
  sendiri opsional.
- Dua bahasa (EN/ID) dengan URL terpisah (`/id/…`), SEO dasar (judul, deskripsi, Open Graph dengan gambar
  sebelum/sesudah, sitemap), aksesibel (WCAG AA), cepat (Lighthouse ≥ 95), gambar galeri WebP/AVIF ber-lazy-load.
- Konten diambil dari sumber kebenaran repo (versi, checksum, changelog, panduan) agar tidak pernah basi.
- **Nanti (opsional)**: demo "coba di browser" dengan mesin di WebAssembly — butuh riset ukuran & kecepatan dulu.

**Selesai bila**: situs terbit di GitHub Pages lewat CI, semua halaman EN/ID, penggeser sebelum/sesudah berjalan di HP
dan desktop, tautan unduh selalu mengarah ke rilis terbaru, Lighthouse ≥ 95 (performa & aksesibilitas).

---

## 6. Urutan & versi

| Tahap | Versi | Isi | Bergantung pada |
|---|---|---|---|
| M8 | 1.2.0 | Tema ×3, Pengaturan, i18n berbasis berkas, opsi hasil | — |
| M9 | 1.3.0 | AI pra-proses (ONNX, unduhan opsional, GPU/CPU) | M8 (Pengaturan) |
| M10a | 1.4.0 | Fitur P1 (palet, format keluaran, tumpuk/potong, hapus latar, bintik, B/W, profil, tempel) | M8 |
| M10b | 1.5.0 | Fitur P2–P3 (centerline, edit ringan, folder pantau, laporan, SVG ramah desain, pintasan) | M10a |
| M11 | — | Website produk | Tangkapan layar M8; galeri & Bandingkan diperbarui tiap rilis |

Setiap tahap: rencana singkat → implementasi → gate penuh (pytest, svelte-check, e2e, bench) → dokumen → commit & push
atas nama pemilik → installer lokal untuk QA. Tag/rilis publik hanya dengan persetujuan pemilik.

## 7. Keputusan yang masih terbuka
1. Kerangka situs: Astro vs Vite + Svelte (rekomendasi: Astro untuk halaman konten statis + komponen Svelte untuk
   penggeser interaktif).
2. Domain situs: `ridhuandev.github.io/png-to-svg-vectorize` dulu atau domain sendiri.
3. Analitik situs: tanpa analitik sama sekali, atau analitik tanpa cookie yang di-host sendiri.
4. Nama produk final untuk situs (tetap "PNG to SVG Vectorize" atau nama merek baru yang lebih mudah diingat).
