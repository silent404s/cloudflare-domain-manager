# Cloudflare Bulk Domain Tool 🚀

A modern, multi-profile Windows desktop application built with Python & CustomTkinter to manage, point, and update DNS records for hundreds of domains on Cloudflare in bulk.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![CustomTkinter](https://img.shields.io/badge/UI-CustomTkinter-darkgreen)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## ✨ Features

- **⚡ Bulk Domain Processing**: Add and point multiple domains to Cloudflare automatically.
- **🎯 Per-Domain Target IP**: Specify custom target IPv4 addresses per domain (`example.com, 103.1.2.3` or `example.com 103.1.2.3`).
- **➕ Subdomain Creator**: Search zones across all saved API profiles and create subdomains on the fly.
- **🔒 Auto SSL & HTTPS**: Automatically sets SSL mode to Flexible and enables *Always Use HTTPS*.
- **⏱️ Configurable Batching**: Adjust batch sizes and request delays to prevent API rate limits (set to `0` for continuous processing).
- **📋 Nameserver & Export Tools**: View grouped nameservers and export antrian data to CSV.
- **🖥️ Responsive Multi-Monitor GUI**: Premium dark-mode UI with window centering and column auto-stretching.
- **📦 Standalone .EXE Support**: Easily compile into a standalone Windows `.exe` application.

---

## 🚀 Quick Start (Running from Source)

### 1. Prerequisites
- Python 3.10+ installed on your system.

### 2. Clone & Install Dependencies
```bash
git clone https://github.com/silent404s/cloudflare-domain-manager.git
cd cloudflare-domain-manager
pip install -r requirements.txt
```

### 3. Configuration
Copy `config.json.example` to `config.json`:
```bash
cp config.json.example config.json
```

### 4. Launch the App
```bash
python main.py
```
*(Or double-click `Launch_App.vbs` on Windows to launch directly without opening a CMD window).*

---

## 📦 Building Standalone Executable (.EXE)

To create a standalone `.exe` file in the `dist/` folder that runs without needing Python:

```bash
python build_exe.py
```
The resulting executable will be available at:
`dist/Cloudflare Bulk Domain Tool.exe`

---

## 🛠️ How to Publish Releases on GitHub

To distribute the app to users so they can download the `.exe` directly without installing Python:

1. Push your repository to GitHub:
   ```bash
   git init
   git add .
   git commit -m "Initial release"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/cloudflare-bulk-domain-tool.git
   git push -u origin main
   ```
2. Go to your GitHub repository -> Click **Releases** -> **Draft a new release**.
3. Create a tag (e.g. `v1.0.0`).
4. Upload `dist/Cloudflare Bulk Domain Tool.exe` under **Attach binaries by dropping them here or selecting them**.
5. Click **Publish release**.

Users can now download and run the `.exe` file directly!

---

## 📄 License
Distributed under the [MIT License](LICENSE).
