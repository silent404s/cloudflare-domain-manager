import threading
import webbrowser
import requests
import customtkinter as ctk
from tkinter import messagebox

CURRENT_VERSION = "1.1.0"

def parse_version(version_str):
    """
    Parses version string like '1.0.0' or 'v1.0.1' into a tuple of integers for comparison.
    """
    cleaned = version_str.strip().lstrip('vV')
    parts = []
    for p in cleaned.split('.'):
        try:
            parts.append(int(p))
        except ValueError:
            parts.append(0)
    return tuple(parts)

def fetch_remote_version_info(update_url, timeout=10):
    """
    Fetches remote version info from a JSON endpoint or GitHub Releases API endpoint.
    Returns dict with keys: version, download_url, release_notes, html_url
    """
    headers = {
        'User-Agent': 'CloudflareBulkDomainTool-UpdateChecker/1.0'
    }
    
    urls_to_try = [update_url]
    if "raw.githubusercontent.com" in update_url:
        if "/main/version.json" in update_url:
            urls_to_try.append(update_url.replace("/main/version.json", "/main/src/version.json"))
        elif "/main/src/version.json" in update_url:
            urls_to_try.append(update_url.replace("/main/src/version.json", "/main/version.json"))

    last_exception = None
    data = None
    for url in urls_to_try:
        try:
            response = requests.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
            data = response.json()
            break
        except Exception as e:
            last_exception = e
            
    if data is None:
        raise last_exception
    
    # Handle GitHub API format ([{tag_name, body, assets...}] or {tag_name...})
    if isinstance(data, list) and len(data) > 0:
        data = data[0]
        
    version = data.get("version") or data.get("tag_name") or "0.0.0"
    release_notes = data.get("release_notes") or data.get("body") or "Tidak ada catatan rilis."
    html_url = data.get("html_url") or data.get("url") or ""
    
    # Try finding asset download url if not explicitly provided
    download_url = data.get("download_url") or ""
    if not download_url and "assets" in data and isinstance(data["assets"], list):
        for asset in data["assets"]:
            if asset.get("name", "").endswith(".exe"):
                download_url = asset.get("browser_download_url", "")
                break
    if not download_url:
        download_url = html_url
        
    return {
        "version": version.strip().lstrip('vV'),
        "download_url": download_url,
        "release_notes": release_notes,
        "html_url": html_url
    }

class UpdateDialog(ctk.CTkToplevel):
    def __init__(self, parent, current_ver, remote_info):
        super().__init__(parent)
        self.title("⚡ Pembaruan Tersedia")
        self.geometry("520x460")
        self.resizable(False, False)
        
        self.remote_info = remote_info
        
        # Center dialog relative to parent window
        self.transient(parent)
        self.grab_set()
        
        # Main Frame
        frame = ctk.CTkFrame(self, corner_radius=10)
        frame.pack(fill="both", expand=True, padx=15, pady=15)
        
        # Header
        lbl_header = ctk.CTkLabel(
            frame, 
            text="🚀 Pembaruan Aplikasi Tersedia!", 
            font=("Segoe UI", 18, "bold"),
            text_color="#10B981"
        )
        lbl_header.pack(pady=(15, 5))
        
        # Version Badge Frame
        ver_frame = ctk.CTkFrame(frame, fg_color="transparent")
        ver_frame.pack(pady=5)
        
        lbl_curr = ctk.CTkLabel(
            ver_frame, 
            text=f"Versi Anda: v{current_ver}", 
            font=("Segoe UI", 12),
            text_color="#9CA3AF"
        )
        lbl_curr.pack(side="left", padx=10)
        
        lbl_new = ctk.CTkLabel(
            ver_frame, 
            text=f"Versi Terbaru: v{remote_info['version']}", 
            font=("Segoe UI", 13, "bold"),
            text_color="#3B82F6"
        )
        lbl_new.pack(side="left", padx=10)
        
        # Release Notes Title
        lbl_notes_title = ctk.CTkLabel(
            frame, 
            text="📋 Catatan Rilis (Release Notes):", 
            font=("Segoe UI", 12, "bold"),
            anchor="w"
        )
        lbl_notes_title.pack(fill="x", padx=15, pady=(10, 5))
        
        # Release Notes Text Box
        txt_notes = ctk.CTkTextbox(frame, font=("Segoe UI", 11), wrap="word")
        txt_notes.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        txt_notes.insert("1.0", remote_info.get("release_notes", "- Tidak ada catatan rilis."))
        txt_notes.configure(state="disabled")
        
        # Action Buttons Frame
        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.pack(fill="x", padx=15, pady=(0, 15))
        
        btn_download = ctk.CTkButton(
            btn_frame, 
            text="🚀 Unduh & Update Setup (.exe)", 
            font=("Segoe UI", 12, "bold"),
            fg_color="#10B981", 
            hover_color="#059669",
            command=self.open_download
        )
        btn_download.pack(side="left", fill="x", expand=True, padx=(0, 5))
        
        btn_close = ctk.CTkButton(
            btn_frame, 
            text="Tutup / Nanti", 
            font=("Segoe UI", 12),
            fg_color="#4B5563", 
            hover_color="#374151",
            command=self.destroy
        )
        btn_close.pack(side="right", padx=(5, 0))

    def open_download(self):
        url = self.remote_info.get("download_url") or self.remote_info.get("html_url")
        if url:
            webbrowser.open(url)
        self.destroy()

def check_for_updates(parent, current_version=CURRENT_VERSION, update_url="", silent=False):
    """
    Performs an update check in a background thread and opens modal dialog on UI thread.
    """
    if not update_url:
        if not silent:
            messagebox.showwarning("Cek Pembaruan", "URL endpoint pembaruan belum dikonfigurasi di config.json.")
        return

    def worker():
        try:
            info = fetch_remote_version_info(update_url)
            remote_ver = info["version"]
            
            if parse_version(remote_ver) > parse_version(current_version):
                parent.after(0, lambda: UpdateDialog(parent, current_version, info))
            else:
                if not silent:
                    parent.after(0, lambda: messagebox.showinfo(
                        "Cek Pembaruan", 
                        f"Aplikasi Anda sudah menggunakan versi terbaru (v{current_version})."
                    ))
        except Exception as e:
            if not silent:
                err_msg = str(e)
                parent.after(0, lambda: messagebox.showerror(
                    "Gagal Cek Pembaruan", 
                    f"Tidak dapat mengecek pembaruan:\n{err_msg}"
                ))

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
