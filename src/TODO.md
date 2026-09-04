# 📋 TODO List & Panduan Lanjutan Project

File ini berisi daftar langkah (To-Do List) yang perlu Anda lakukan ketika ingin melanjutkan project ini di kemudian hari.

---

## 🟢 1. Menjalankan Aplikasi Saat Ini
- [x] **Tanpa CMD (Shortcut Instan)**: Double-click file [`Launch_App.vbs`](file:///c:/Users/skylark/Downloads/pointerdomain/Launch_App.vbs)
- [x] **File Standalone Executable (.exe)**: Double-click file [`dist\Cloudflare Bulk Domain Tool.exe`](file:///c:/Users/skylark/Downloads/pointerdomain/dist/Cloudflare%20Bulk%20Domain%20Tool.exe)
- [x] **Manual Python**: Buka CMD -> `python main.py`

---

## 🛠️ 2. Langkah Membuat Installer Windows Resmi (`Setup.exe`)
Gunakan langkah ini jika Anda ingin membuat file setup installer resmi dengan wizard (*Next -> Install -> Finish*) dan ikon shortcut desktop otomatis:

- [ ] **Langkah 1**: Download dan install aplikasi gratis **Inno Setup**:
  👉 [Download Inno Setup Installer](https://jrsoftware.org/isdl.php)
- [ ] **Langkah 2**: Buka aplikasi Inno Setup -> Pilih **Open an existing script file** -> Pilih file [`installer_setup.iss`](file:///c:/Users/skylark/Downloads/pointerdomain/installer_setup.iss).
- [ ] **Langkah 3**: Klik menu **Build** -> **Compile** (atau tekan tombol `Ctrl + F9`).
- [ ] **Langkah 4**: File installer resmi **`CloudflareBulkDomain_Setup_v1.0.exe`** akan selesai dibuat di dalam folder `Output/`.

---

## 🌐 3. Langkah Upload & Git Push ke GitHub Publik
Ketika Anda siap meng-upload kode project ini ke akun GitHub Anda:

- [ ] **Langkah 1**: Buka [GitHub.com](https://github.com) -> Buat Repository baru (nama misal: `cloudflare-bulk-domain-tool`).
- [ ] **Langkah 2**: Buka CMD / Terminal di folder project ini, lalu jalankan perintah berikut:
  ```bash
  # Commit perubahan kode
  git commit -m "Initial Release: Cloudflare Bulk Domain Tool v1.0"

  # Set branch utama ke main
  git branch -M main

  # Hubungkan ke repository GitHub Anda (ganti USERNAME_ANDA dengan username GitHub Anda)
  git remote add origin https://github.com/USERNAME_ANDA/cloudflare-bulk-domain-tool.git

  # Upload ke GitHub
  git push -u origin main
  ```
  *(Catatan: API Key Cloudflare Anda di `config.json` sudah 100% terkunci oleh `.gitignore` dan TIDAK AKAN ikut ter-upload).*

---

## 📦 4. Langkah Mempublikasikan Installer / .EXE di GitHub Releases
Agar pengguna lain di internet bisa langsung mengunduh file `.exe` atau `Setup.exe` dari halaman GitHub Anda tanpa perlu menginstall Python:

- [ ] **Langkah 1**: Buka repository GitHub Anda di browser -> Klik tab **Releases** (di bagian kanan).
- [ ] **Langkah 2**: Klik tombol **Draft a new release**.
- [ ] **Langkah 3**: Isi **Tag version** (misal: `v1.0.0`) dan judul release (misal: `Release Cloudflare Bulk Domain Tool v1.0`).
- [ ] **Langkah 4**: Drag & Drop file **`dist\Cloudflare Bulk Domain Tool.exe`** (atau file Setup installer) ke kotak *Attach binaries*.
- [ ] **Langkah 5**: Klik **Publish release**.

---

## ⚙️ 5. Re-Build `.exe` Jika Mengubah Kode Nanti
- [ ] Jika di kemudian hari Anda mengedit file kode `.py` dan ingin memperbarui file `.exe`:
  ```bash
  python build_exe.py
  ```
