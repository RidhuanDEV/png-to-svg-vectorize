# PNG to SVG Vectorize — panduan pengguna

Ubah ilustrasi raster (PNG, WebP, JPEG) menjadi berkas SVG yang rapi dan bisa diedit: isian gradien yang halus, garis
tepi yang tajam, bentuk `<path>` murni yang bisa dipakai di browser, Figma, Illustrator, Inkscape, dan framework
aplikasi. Semua diproses di komputer Anda — tidak ada yang diunggah, tidak ada pelacakan.

*English: [user-guide.en.md](user-guide.en.md)*

![Jendela utama](images/app-overview.png)

## 1. Instalasi

Unduh rilis terbaru dari
[halaman GitHub Releases](https://github.com/RidhuanDEV/png-to-svg-vectorize/releases).

### Windows 10 / 11 (64-bit)

1. Unduh `PNG-to-SVG-Vectorize-Setup-x.y.z.exe` lalu jalankan. Aplikasi terpasang untuk pengguna Anda saja; tidak
   perlu hak administrator.
2. Aplikasi ini gratis dan open source sehingga **tidak ditandatangani (code signing)**. Windows SmartScreen bisa
   menampilkan *"Windows protected your PC"*. Klik **More info → Run anyway**.
3. Aplikasi membutuhkan **WebView2 Runtime** dari Microsoft Edge. Sudah ada di Windows 11 dan hampir semua Windows 10.
   Bila installer memberi tahu bahwa komponen ini tidak ada, pasang *Evergreen Runtime* dari
   <https://developer.microsoft.com/microsoft-edge/webview2/>.

Tidak mau memakai installer? Pakai `PNG-to-SVG-Vectorize-x.y.z-windows-x64-portable.zip`: ekstrak di mana saja lalu
jalankan `PNG to SVG Vectorize.exe`.

### macOS 12 atau lebih baru

1. Unduh DMG sesuai Mac Anda: `…-arm64.dmg` untuk Apple Silicon (M1 ke atas), `…-x64.dmg` untuk Mac Intel.
2. Buka DMG, lalu seret **PNG to SVG Vectorize** ke folder **Applications**.
3. Aplikasi **belum dinotarisasi** oleh Apple, jadi pembukaan pertama diblokir. Buka **System Settings → Privacy &
   Security**, gulir ke bawah, klik **Open Anyway** di samping pesan tentang PNG to SVG Vectorize, lalu konfirmasi.
   (Di macOS 14 ke bawah, klik kanan aplikasi → **Open** juga bisa.)
4. Bila macOS mengatakan aplikasi "rusak dan tidak bisa dibuka" (*is damaged*), hapus tanda karantina unduhan lewat
   Terminal:

   ```bash
   xattr -dr com.apple.quarantine "/Applications/PNG to SVG Vectorize.app"
   ```

## 2. Mengonversi gambar

1. **Tambahkan gambar**: seret satu atau beberapa berkas PNG, WebP, atau JPEG ke mana saja di jendela, atau klik
   **Buka gambar…**. Batas: 50 MB per berkas, sisi terpanjang maksimal 8000 px.
2. Setiap gambar muncul di daftar **Gambar** beserta progresnya (mencari garis tinta → mencari wilayah warna →
   menyusun kurva → menulis SVG). Ilustrasi 1536×1024 biasanya selesai dalam 5–10 detik; beberapa gambar diproses
   bersamaan.
3. Klik gambar di daftar untuk menampilkannya. ■ untuk membatalkan, ↻ untuk memproses lagi, ✕ untuk menghapus.

## 3. Membandingkan asli dan SVG

- **Berdampingan**: gambar asli di kiri, SVG di kanan. Gulir untuk zoom (hingga 800%), seret untuk menggeser — kedua
  sisi bergerak bersama. **Pas** (atau tombol `0`) menampilkan seluruh gambar; tombol `+` / `-` dan panah juga bisa.
- **Geser**: satu tampilan dengan garis pembatas; seret pegangannya (atau ← →) untuk membandingkan.
- **Lapisan**: tampilkan *Semua*, *Isian saja*, atau *Garis saja* untuk memeriksa tiap bagian SVG.
- **Hasil** menampilkan **kemiripan** (seberapa mirip tampilan SVG dengan aslinya, 100% = identik; hasil yang baik
  sekitar 98–99%), jumlah wilayah, gradien, dan bentuk garis, ukuran berkas, serta waktu proses.

Selalu periksa detail di perbesaran 200% atau lebih: satu angka bisa menyembunyikan cacat kecil di satu bagian.

## 4. Pengaturan

**Preset** — pilih yang sesuai dengan gambar sebelum menambahkan gambar (atau proses ulang setelahnya):

| Preset | Untuk |
|---|---|
| Kartun | karakter dengan garis tinta gelap dan bayangan halus (bawaan) |
| Ilustrasi datar | bentuk warna solid dengan sedikit garis; hanya gradien yang jelas dipertahankan |
| Logo / ikon | sedikit warna datar dan geometri tepat; tanpa gradien |
| Foto → poster | foto atau lukisan menjadi vektor bergaya poster dengan wilayah lebih sedikit dan besar |

Pengaturan **Lanjutan** (ubah, lalu klik **Proses ulang gambar terpilih**):

| Pengaturan | Efek |
|---|---|
| Pisahkan garis tinta | garis gelap menjadi lapisan tersendiri yang tajam |
| Isian gradien / Gradien radial | bayangan halus sebagai gradien; mati = warna datar |
| Toleransi kurva | lebih besar = titik kurva lebih sedikit & berkas lebih kecil; lebih kecil = lebih dekat ke piksel |
| Penghalusan | lebih besar = batas antar-warna lebih halus |
| Gabung warna mirip (ΔE) | lebih besar = wilayah lebih sedikit (lebih sederhana); lebih kecil = lebih detail |
| Detail garis | resolusi untuk menelusuri garis (otomatis biasanya sudah tepat) |

Gambar baru selalu memakai pengaturan saat itu. **Kembalikan ke preset** memulihkan nilai bawaan.

## 5. Menyimpan

- **Simpan SVG** menyimpan hasil yang dipilih (aplikasi menanyakan lokasinya).
- **Simpan semua** menyimpan semua hasil yang sudah selesai ke folder pilihan Anda; berkas yang sudah ada tidak pernah
  ditimpa (dipakai `nama-2.svg`).
- **Salin kode SVG** menyalin markup SVG ke clipboard, siap ditempel ke kode atau aplikasi desain.

ID gradien unik per berkas, jadi banyak SVG bisa disisipkan di satu halaman web.

## 6. Tips agar hasil terbaik

- Paling cocok untuk ilustrasi yang bersih: kartun, gambar datar, ikon, logo. Foto menghasilkan banyak wilayah (pakai
  *Foto → poster*).
- Pakai versi terbesar dan paling tajam yang Anda punya (sekitar 1000–2000 px di sisi terpanjang). Hindari JPEG yang
  terkompresi berat: noise-nya menjadi wilayah-wilayah kecil.
- Bila detail kecil hilang, turunkan *Gabung warna mirip*; bila berkas terlalu besar, naikkan *Toleransi kurva*.

## 7. Privasi

Aplikasi menjalankan layanan kecil di dalam dirinya yang hanya menerima koneksi dari komputer yang sama (`127.0.0.1`)
dan hanya dengan kunci acak yang dibuat setiap sesi. Gambar dan hasil disimpan di memori dan hilang saat aplikasi
ditutup. Tidak ada telemetri dan tidak ada akses jaringan ke luar komputer Anda.

## 8. Pemecahan masalah

| Masalah | Solusi |
|---|---|
| Windows: jendela kosong atau aplikasi langsung tertutup | Pasang WebView2 Runtime (lihat Instalasi). |
| Windows: antivirus mengarantina aplikasi | Aplikasi tanpa tanda tangan yang dibuat dengan PyInstaller kadang ditandai. Pulihkan dan tambahkan pengecualian, atau bangun sendiri dari kode sumber. |
| macOS: "can't be opened" / "damaged" | Lihat Instalasi, langkah 3–4. |
| "Tidak diterima — 413" | Berkas lebih dari 50 MB atau 8000 px; perkecil dulu. |
| "Tidak diterima — 415" | Bukan gambar PNG, WebP, atau JPEG (yang diperiksa isi berkas, bukan namanya). |
| Masalah lain | Aplikasi menulis log: Windows `%LOCALAPPDATA%\PNG to SVG Vectorize\app.log`, macOS `~/Library/Application Support/PNG to SVG Vectorize/app.log`. Lampirkan di [GitHub issue](https://github.com/RidhuanDEV/png-to-svg-vectorize/issues) (log tidak berisi data gambar). |

## 9. Baris perintah dan Python

Mesin yang sama tersedia tanpa aplikasi (Python 3.10+):
`pip install "png-to-svg-vectorize @ git+https://github.com/RidhuanDEV/png-to-svg-vectorize"`, lalu
`png2svg gambar.png`. Lihat [README](../README.md) untuk opsi, UI browser (`png2svg serve`), dan API Python.
