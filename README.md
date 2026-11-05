# Rinova Pro — Android Storage & System Doctor (Konter Edition)

**Rinova Pro** adalah aplikasi desktop modern (Windows 11 Fluent Design) untuk diagnosa dan perbaikan mendalam masalah penyimpanan Android, pemulihan database rusak (*corrupted MediaProvider*), dan *universal debloating* tanpa resiko kehilangan data pengguna.

---

## ⚡ Fitur Utama

1. **Deep Storage Diagnostic:**
   - Memindai partisi fisik `/data` dan mendeteksi pembengkakan tersembunyi.
   - Mendeteksi anomali database SQLite MediaStorage (`external.db` hingga 30+ GB).
   - Menampilkan visualisasi penggunaan ruang (Aplikasi vs Bloat vs Bebas).
   - Menampilkan 10 aplikasi dengan konsumsi *App Data* terbesar.

2. **1-Click Safe Storage Recovery (Anti Hilang Data):**
   - Mengosongkan puluhan GB ruang memori akibat loop database SQLite.
   - Memicu otomatis *MediaScanner broadcast* untuk membangun ulang indeks galeri secara bersih.
   - **100% Aman:** Foto, video, dokumen, dan chat WhatsApp tidak dihapus.

3. **Universal Android Debloater:**
   - Preset aman untuk: **Samsung (One UI)**, **Xiaomi (HyperOS/MIUI)**, **Infinix/Tecno (Transsion)**, **Oppo/Realme/Vivo (BBK)**, dan **Google Non-Esensial**.
   - Menghilangkan *adware* (IronSource Aura, Glance), pelacak telemetri, dan bloatware pabrikan.

4. **Wireless ADB Wizard:**
   - Asisten pairing & koneksi nirkabel untuk Android 11+ tanpa harus colok kabel USB.

---

## 🚀 Cara Uji Coba Langsung di Browser (Live Preview)

Anda bisa menguji coba tampilan dan fungsi secara lokal tanpa install dependensi berat:

```bash
cd "rinova-pro"
python3 preview_server.py 8080
```

Lalu buka di browser HP / PC: `http://localhost:8080`

---

## 👨‍💻 Lead Architect & Creator

**Sahal Arbani**  
- **TikTok Portfolio:** [@saha.arbani](https://www.tiktok.com/@saha.arbani)
- **Role:** Systems & Reverse Engineering, Android Internal Diagnostics Suite
- **Engineering Highlights:** Solusi pemulihan 36+ GB database SQLite MediaStore terkorupsi, non-destructive storage remediation, dynamic ADB heuristics.

---

## 📦 Cara Build Menjadi File `.exe` via GitHub Actions

Tidak perlu kompilasi di laptop lokal Anda! GitHub Actions akan melakukan kompilasi otomatis di cloud Windows resmi Microsoft:

1. Push folder `rinova-pro` ini ke repository GitHub Anda:
   ```bash
   git init
   git add .
   git commit -m "feat: Initial commit Rinova Pro"
   git branch -M main
   git remote add origin https://github.com/USERNAME/rinova-pro.git
   git push -u origin main
   ```
2. Buka tab **Actions** di GitHub repository Anda.
3. Workflow **"Build Rinova Pro Windows Executable"** akan otomatis berjalan.
4. Setelah selesai (sekitar 2–3 menit), unduh file **`RinovaPro-Windows-Portable.zip`** di bagian *Artifacts*.
5. Ekstrak zip tersebut di PC konter teman Anda, lalu **klik 2x `RinovaPro.exe`**!
