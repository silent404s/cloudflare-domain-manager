import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, filedialog
import threading
import json
import traceback

import ipaddress
import config_manager
import export_utils
import update_checker
from logger import app_logger
from queue_manager import QueueManager
from cloudflare_api import CloudflareAPI, find_zone_across_profiles, check_domain_ip_and_profile

def is_valid_ipv4(ip):
    if not ip:
        return False
    try:
        ipaddress.IPv4Address(ip)
        return True
    except ValueError:
        return False

def center_window_over_parent(window, parent, width=None, height=None):
    """
    Centers a CTkToplevel / Toplevel window directly over its parent window,
    ensuring it stays on the exact same monitor screen.
    """
    try:
        parent.update_idletasks()
        window.update_idletasks()
        
        if width is None:
            width = window.winfo_width()
        if height is None:
            height = window.winfo_height()
            
        p_x = parent.winfo_x()
        p_y = parent.winfo_y()
        p_w = parent.winfo_width()
        p_h = parent.winfo_height()
        
        x = p_x + max(0, (p_w - width) // 2)
        y = p_y + max(0, (p_h - height) // 2)
        
        window.geometry(f"{width}x{height}+{x}+{y}")
    except Exception as e:
        app_logger.error(f"Error centering window: {e}")

def parse_nameservers_list(ns_string):
    if not ns_string:
        return []
    cleaned = str(ns_string).replace(';', ',').replace('\n', ',')
    parts = [p.strip() for p in cleaned.split(',') if p.strip()]
    res = []
    for p in parts:
        if p not in res:
            res.append(p)
    return res

class ShowErrorDialog(ctk.CTkToplevel):
    def __init__(self, parent, domain, error_msg):
        super().__init__(parent)
        self.parent = parent
        self.domain = domain
        self.error_msg = error_msg

        self.title(f"⚠️ Detail Error - {domain}")
        self.geometry("540x380")
        self.resizable(True, True)
        self.configure(fg_color="#202020")

        self.custom_font = ctk.CTkFont(family="Segoe UI", size=11)
        self.bold_font = ctk.CTkFont(family="Segoe UI", size=12, weight="bold")
        self.log_font = ctk.CTkFont(family="Consolas", size=10)

        self.build_ui()
        center_window_over_parent(self, parent, 540, 380)
        self.grab_set()

    def build_ui(self):
        header = ctk.CTkFrame(self, fg_color="#282828", corner_radius=8)
        header.pack(fill="x", padx=15, pady=(15, 10))

        ctk.CTkLabel(header, text=f"⚠️ Detail Error: {self.domain}", font=self.bold_font, text_color="#F87171").pack(anchor="w", padx=15, pady=10)

        content_frame = ctk.CTkFrame(self, fg_color="#282828", corner_radius=8)
        content_frame.pack(fill="both", expand=True, padx=15, pady=(0, 10))

        textbox = ctk.CTkTextbox(content_frame, font=self.log_font, fg_color="#1E1E1E", text_color="#FCA5A5", border_color="#444444", border_width=1, corner_radius=6)
        textbox.pack(fill="both", expand=True, padx=10, pady=10)
        textbox.insert("1.0", self.error_msg)
        textbox.configure(state="disabled")

        btn_bar = ctk.CTkFrame(self, fg_color="transparent")
        btn_bar.pack(fill="x", padx=15, pady=(0, 15))

        ctk.CTkButton(btn_bar, text="📋 Copy Text Error", font=self.bold_font, command=self.copy_error, fg_color="#0284C7", hover_color="#0369A1", width=140, height=32, corner_radius=8).pack(side="left")
        ctk.CTkButton(btn_bar, text="Tutup", font=self.custom_font, command=self.destroy, fg_color="#2D2D2D", hover_color="#353535", width=90, height=32, corner_radius=8).pack(side="right")

    def copy_error(self):
        self.clipboard_clear()
        self.clipboard_append(self.error_msg)
        self.update()
        messagebox.showinfo("Berhasil Copied", "Pesan error berhasil disalin ke clipboard!", parent=self)

class AddProfileDialog(ctk.CTkToplevel):
    def __init__(self, parent, config, on_success_callback):
        super().__init__(parent)
        self.parent = parent
        self.config = config
        self.on_success_callback = on_success_callback
        
        self.title("Tambah Profil Cloudflare Baru")
        self.resizable(False, False)
        self.configure(fg_color="#202020")
        
        self.custom_font = ctk.CTkFont(family="Segoe UI", size=11)
        self.bold_font = ctk.CTkFont(family="Segoe UI", size=11, weight="bold")
        
        self.build_ui()
        center_window_over_parent(self, parent, 440, 350)
        self.grab_set()
        
    def build_ui(self):
        ctk.CTkLabel(self, text="Tambah Profil Cloudflare Baru", font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold")).pack(pady=(15, 10))
        
        frame = ctk.CTkFrame(self, fg_color="#282828", corner_radius=8)
        frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        
        # Profile Name
        ctk.CTkLabel(frame, text="Nama Profil / Label Akun:", font=self.custom_font).pack(anchor="w", padx=15, pady=(10, 2))
        self.name_entry = ctk.CTkEntry(frame, placeholder_text="contoh: Akun CF 2, Domain Utama, dll", font=self.custom_font, fg_color="#1E1E1E", border_color="#444444", corner_radius=8)
        self.name_entry.pack(fill="x", padx=15, pady=(0, 10))
        
        # Auth Method Selection
        self.auth_var = ctk.StringVar(value="token")
        auth_frame = ctk.CTkFrame(frame, fg_color="transparent")
        auth_frame.pack(fill="x", padx=15, pady=(0, 5))
        
        ctk.CTkRadioButton(auth_frame, text="API Token", font=self.custom_font, variable=self.auth_var, value="token", command=self.toggle_auth).pack(side="left", padx=(0, 10))
        ctk.CTkRadioButton(auth_frame, text="Global API Key", font=self.custom_font, variable=self.auth_var, value="global", command=self.toggle_auth).pack(side="left")
        
        # Entries Container Frame
        self.input_frame = ctk.CTkFrame(frame, fg_color="transparent")
        self.input_frame.pack(fill="x", padx=15, pady=5)
        
        self.token_entry = ctk.CTkEntry(self.input_frame, placeholder_text="Cloudflare API Token", show="*", font=self.custom_font, fg_color="#1E1E1E", border_color="#444444", corner_radius=8)
        self.token_entry.pack(fill="x", pady=4)
        
        self.email_entry = ctk.CTkEntry(self.input_frame, placeholder_text="Cloudflare Email", font=self.custom_font, fg_color="#1E1E1E", border_color="#444444", corner_radius=8)
        self.global_key_entry = ctk.CTkEntry(self.input_frame, placeholder_text="Global API Key", show="*", font=self.custom_font, fg_color="#1E1E1E", border_color="#444444", corner_radius=8)
        
        # Buttons
        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.pack(fill="x", padx=15, pady=(15, 10))
        
        ctk.CTkButton(btn_frame, text="Batal", font=self.custom_font, width=90, fg_color="#2D2D2D", hover_color="#353535", command=self.destroy, corner_radius=8).pack(side="right", padx=(5, 0))
        ctk.CTkButton(btn_frame, text="Simpan Profil", font=self.bold_font, width=130, fg_color="#0284C7", hover_color="#0369A1", command=self.save_profile, corner_radius=8).pack(side="right")

    def toggle_auth(self):
        method = self.auth_var.get()
        if method == "token":
            self.email_entry.pack_forget()
            self.global_key_entry.pack_forget()
            self.token_entry.pack(fill="x", pady=4)
        else:
            self.token_entry.pack_forget()
            self.email_entry.pack(fill="x", pady=4)
            self.global_key_entry.pack(fill="x", pady=4)

    def save_profile(self):
        name = self.name_entry.get().strip()
        if not name:
            messagebox.showerror("Error", "Masukkan Nama Profil.", parent=self)
            return
            
        if name in self.config.get("api_profiles", {}):
            messagebox.showerror("Error", f"Profil '{name}' sudah ada.", parent=self)
            return
            
        method = self.auth_var.get()
        token = self.token_entry.get().strip()
        email = self.email_entry.get().strip()
        global_key = self.global_key_entry.get().strip()
        
        if method == "token" and not token:
            messagebox.showerror("Error", "Masukkan Cloudflare API Token.", parent=self)
            return
        elif method == "global" and (not email or not global_key):
            messagebox.showerror("Error", "Masukkan Email dan Global API Key.", parent=self)
            return

        if "api_profiles" not in self.config:
            self.config["api_profiles"] = {}

        self.config["api_profiles"][name] = {
            "api_token": token,
            "global_api_key": global_key,
            "email": email,
            "auth_method": method
        }
        self.config["current_profile"] = name
        config_manager.save_config(self.config)
        
        app_logger.info(f"Profil CF baru '{name}' berhasil dibuat dan disimpan.")
        messagebox.showinfo("Berhasil", f"Profil '{name}' berhasil disimpan!", parent=self.parent)
        
        self.on_success_callback(name)
        self.destroy()

class RedirectRulesDialog(ctk.CTkToplevel):
    def __init__(self, parent, config, initial_domain=""):
        super().__init__(parent)
        self.parent = parent
        self.config = config
        self.initial_domain = initial_domain
        
        self.title("Cloudflare Redirect Rules Manager")
        self.geometry("780x820")
        self.minsize(720, 750)
        self.configure(fg_color="#202020")
        
        self.custom_font = ctk.CTkFont(family="Segoe UI", size=11)
        self.bold_font = ctk.CTkFont(family="Segoe UI", size=11, weight="bold")
        self.log_font = ctk.CTkFont(family="Consolas", size=10)
        
        self.rule_rows = [] # list of dicts: {'frame': ..., 'path_entry': ..., 'target_entry': ...}
        
        self.build_ui()
        center_window_over_parent(self, parent, 780, 820)
        self.grab_set()
        
    def build_ui(self):
        ctk.CTkLabel(self, text="⚡ Cloudflare Single Redirect Rules Manager", font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold")).pack(pady=(10, 4))
        
        # 1. Action Buttons Pinned at Bottom of Window
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(side="bottom", fill="x", padx=15, pady=(0, 12))
        
        self.btn_cancel = ctk.CTkButton(btn_frame, text="Tutup", font=self.custom_font, width=95, height=34, fg_color="#2D2D2D", hover_color="#353535", command=self.destroy, corner_radius=8)
        self.btn_cancel.pack(side="right", padx=(8, 0))
        
        self.btn_submit = ctk.CTkButton(btn_frame, text="⚡ Mulai Buat / Update Rules", font=self.bold_font, width=220, height=34, fg_color="#7C3AED", hover_color="#6D28D9", command=self.start_process, corner_radius=8)
        self.btn_submit.pack(side="right")

        # 2. Main Frame Fills Available Space Above Action Buttons
        main_frame = ctk.CTkFrame(self, fg_color="#282828", corner_radius=8)
        main_frame.pack(side="top", fill="both", expand=True, padx=12, pady=(0, 8))
        
        # Profile / Token Selector Section
        token_frame = ctk.CTkFrame(main_frame, fg_color="#1E1E1E", corner_radius=6)
        token_frame.pack(fill="x", padx=10, pady=(8, 4))
        
        ctk.CTkLabel(token_frame, text="Pilih Profil CF / Token untuk Memproses Rules:", font=self.bold_font, text_color="#A78BFA").pack(anchor="w", padx=10, pady=(5, 1))
        
        profiles = list(self.config.get("api_profiles", {}).keys())
        profile_options = ["Auto-Detect (Cari otomatis di semua profil)", "Gunakan Token CF Khusus (Kolom di Bawah)"] + [f"Profil: {p}" for p in profiles]
        
        saved_sel_prof = self.config.get("rules_selected_profile", profile_options[0])
        if saved_sel_prof not in profile_options:
            saved_sel_prof = profile_options[0]

        self.profile_select_var = ctk.StringVar(value=saved_sel_prof)
        self.profile_dropdown = ctk.CTkOptionMenu(token_frame, variable=self.profile_select_var, values=profile_options, font=self.custom_font, corner_radius=6)
        self.profile_dropdown.pack(fill="x", padx=10, pady=(0, 4))

        self.token_entry = ctk.CTkEntry(token_frame, placeholder_text="Atau Tempelkan Token CF Khusus di sini jika memilih 'Gunakan Token CF Khusus'...", show="*", font=self.custom_font, fg_color="#282828", border_color="#444444")
        self.token_entry.pack(fill="x", padx=10, pady=(0, 6))
        
        saved_rules_token = self.config.get("rules_custom_token", "")
        if saved_rules_token:
            self.token_entry.insert(0, saved_rules_token)

        # Root Rule Settings Section
        root_frame = ctk.CTkFrame(main_frame, fg_color="#1E1E1E", corner_radius=6)
        root_frame.pack(fill="x", padx=10, pady=4)
        
        self.root_enabled_var = tk.BooleanVar(value=True)
        chk_root = ctk.CTkCheckBox(root_frame, text="Otomatis buat Root Rule jika BELUM ADA di CF (Rule 'Root', Order: Last, 302, Preserve Query: OFF)", font=self.bold_font, variable=self.root_enabled_var, text_color="#38BDF8")
        chk_root.pack(anchor="w", padx=10, pady=(6, 2))
        
        root_input_frame = ctk.CTkFrame(root_frame, fg_color="transparent")
        root_input_frame.pack(fill="x", padx=10, pady=(0, 6))
        
        ctk.CTkLabel(root_input_frame, text="Target URL Root (Tujuan Wajib):", font=self.custom_font).pack(side="left", padx=(0, 5))
        self.root_url_entry = ctk.CTkEntry(root_input_frame, placeholder_text="https://www.youtube.com/", font=self.custom_font, fg_color="#282828", border_color="#444444")
        self.root_url_entry.pack(side="left", fill="x", expand=True)
        self.root_url_entry.insert(0, "https://www.youtube.com/")

        # Path Rules Search & Input Section
        search_frame = ctk.CTkFrame(main_frame, fg_color="#1E1E1E", corner_radius=6)
        search_frame.pack(fill="x", padx=10, pady=(4, 2))
        
        ctk.CTkLabel(search_frame, text="🔍 Cari Path Rule untuk Ubah Tujuan:", font=self.bold_font, text_color="#38BDF8").pack(side="left", padx=(10, 5), pady=4)
        
        self.search_entry = ctk.CTkEntry(search_frame, placeholder_text="domain.com/path", font=self.custom_font, fg_color="#282828", border_color="#444444")
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(0, 6), pady=4)
        
        btn_search = ctk.CTkButton(search_frame, text="🔍 Cari Rule", font=self.bold_font, width=100, height=26, fg_color="#0284C7", hover_color="#0369A1", command=self.search_single_rule, corner_radius=6)
        btn_search.pack(side="right", padx=(0, 10), pady=4)

        # Header for 2-column input table
        rules_header_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        rules_header_frame.pack(fill="x", padx=10, pady=(4, 2))
        ctk.CTkLabel(rules_header_frame, text="Form Buat / Edit Path Rules (Order: First, 302, Preserve Query: ON):", font=self.bold_font).pack(side="left")

        # Scrollable Frame for 2-column rows
        self.scroll_frame = ctk.CTkScrollableFrame(main_frame, fg_color="#1E1E1E", height=135, corner_radius=6)
        self.scroll_frame.pack(fill="x", padx=10, pady=2)
        
        # Header inside scroll frame
        col_header = ctk.CTkFrame(self.scroll_frame, fg_color="#282828", height=26)
        col_header.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(col_header, text="Domain + Path (contoh: domain.com/path)", font=self.bold_font, width=280).pack(side="left", padx=5)
        ctk.CTkLabel(col_header, text="Target URL Tujuan (contoh: https://tujuan.com/landing)", font=self.bold_font).pack(side="left", padx=5)

        # Row Management Buttons
        row_btn_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        row_btn_frame.pack(fill="x", padx=10, pady=4)
        
        ctk.CTkButton(row_btn_frame, text="+ Tambah Baris Rule", font=self.custom_font, width=130, height=26, command=self.add_rule_row, fg_color="#2D2D2D", hover_color="#353535", border_width=1, border_color="#3D3D3D", corner_radius=6).pack(side="left")
        ctk.CTkButton(row_btn_frame, text="Clear Semua Baris", font=self.custom_font, width=120, height=26, command=self.clear_all_rows, fg_color="#8A1A23", hover_color="#A11E29", corner_radius=6).pack(side="left", padx=8)

        # Add initial clean default rows
        if self.initial_domain:
            self.add_rule_row(domain_path=f"{self.initial_domain}/path", target_url="https://tujuan.com/landing")
        else:
            self.add_rule_row(domain_path="", target_url="")

        # Progress Bar & Log Output
        self.progress_var = tk.DoubleVar(value=0)
        self.progress = ctk.CTkProgressBar(main_frame, variable=self.progress_var)
        self.progress.pack(fill="x", padx=10, pady=4)
        
        self.log_box = ctk.CTkTextbox(main_frame, height=75, font=self.log_font, fg_color="#1E1E1E", border_color="#444444", border_width=1, corner_radius=6)
        self.log_box.pack(fill="x", padx=10, pady=(0, 6))
        self.log_box.configure(state="disabled")

    def add_rule_row(self, domain_path="", target_url=""):
        row_frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        row_frame.pack(fill="x", pady=2)
        
        path_entry = ctk.CTkEntry(row_frame, placeholder_text="domain.com/path", font=self.custom_font, fg_color="#282828", border_color="#444444")
        path_entry.pack(side="left", fill="x", expand=True, padx=(0, 4))
        if domain_path:
            path_entry.insert(0, domain_path)
            
        target_entry = ctk.CTkEntry(row_frame, placeholder_text="https://tujuan-custom.com/...", font=self.custom_font, fg_color="#282828", border_color="#444444")
        target_entry.pack(side="left", fill="x", expand=True, padx=(0, 4))
        if target_url:
            target_entry.insert(0, target_url)
            
        row_dict = {'frame': row_frame, 'path_entry': path_entry, 'target_entry': target_entry}
        
        btn_del = ctk.CTkButton(row_frame, text="✕", width=28, height=28, fg_color="#8A1A23", hover_color="#A11E29", command=lambda r=row_dict: self.remove_rule_row(r))
        btn_del.pack(side="right")
        
        self.rule_rows.append(row_dict)

    def remove_rule_row(self, row_dict):
        if row_dict in self.rule_rows:
            self.rule_rows.remove(row_dict)
            row_dict['frame'].destroy()

    def clear_all_rows(self):
        for r in list(self.rule_rows):
            r['frame'].destroy()
        self.rule_rows = []

    def resolve_api_and_zone_for_domain(self, domain_str, custom_token=None):
        selected_mode = self.profile_select_var.get() if hasattr(self, 'profile_select_var') else "Auto-Detect"

        # 1. If user selected a specific profile (e.g. "Profil: cf rules nagawin")
        if selected_mode.startswith("Profil: "):
            prof_name = selected_mode.replace("Profil: ", "").strip()
            if prof_name in self.config.get("api_profiles", {}):
                temp_config = self.config.copy()
                temp_config["current_profile"] = prof_name
                api = CloudflareAPI(temp_config, profile_name=prof_name)
                zone_id, zone_name, ns_list = api.find_zone(domain_str)
                if zone_id:
                    return prof_name, api, zone_id, zone_name, ns_list, None
                return None, None, None, None, None, f"Domain '{domain_str}' tidak ditemukan pada profil '{prof_name}'."

        # 2. If user selected "Gunakan Token CF Khusus" or typed custom_token
        if (selected_mode.startswith("Gunakan Token") or custom_token) and custom_token:
            temp_config = self.config.copy()
            temp_config["api_profiles"] = {
                "_custom_rules_profile": {
                    "api_token": custom_token,
                    "auth_method": "token"
                }
            }
            temp_config["current_profile"] = "_custom_rules_profile"
            custom_api = CloudflareAPI(temp_config, profile_name="_custom_rules_profile")
            zone_id, zone_name, ns_list = custom_api.find_zone(domain_str)
            if zone_id:
                return "Token CF Khusus", custom_api, zone_id, zone_name, ns_list, None

        # 3. Check if domain exists in self.parent.domains_data with assigned profile
        for item in self.parent.domains_data:
            if item.get('domain') == domain_str and item.get('profile'):
                target_prof = item['profile']
                temp_config = self.config.copy()
                temp_config["current_profile"] = target_prof
                prof_api = CloudflareAPI(temp_config, profile_name=target_prof)
                zone_id, zone_name, ns_list = prof_api.find_zone(domain_str)
                if zone_id:
                    return target_prof, prof_api, zone_id, zone_name, ns_list, None

        # 4. Fallback: Search across all saved profiles
        return find_zone_across_profiles(self.config, domain_str)

    def search_single_rule(self):
        query = self.search_entry.get().strip()
        if not query:
            messagebox.showwarning("Peringatan", "Masukkan domain/path yang ingin dicari (contoh: domain.com/path).", parent=self)
            return
            
        if '://' in query:
            query = query.split('://', 1)[1]
            
        if '/' in query:
            dom, path = query.split('/', 1)
            path = '/' + path.strip('/')
        else:
            dom = query
            path = '/root'
            
        dom = dom.strip().lower()
        custom_token = self.token_entry.get().strip() or None
        
        self.append_log(f"[{dom}] Mencari rule '{path}' di Cloudflare...")
        
        prof_name, api, zone_id, zone_name, ns_list, err_msg = self.resolve_api_and_zone_for_domain(dom, custom_token)
        if not zone_id:
            messagebox.showerror("Error", err_msg or f"Domain '{dom}' tidak ditemukan pada profil CF manapun.", parent=self)
            return

        success, rule, msg = api.find_specific_redirect_rule(zone_id, path, custom_token=custom_token)
        if not success:
            messagebox.showerror("Error", f"Gagal mencari rule di CF:\n{msg}", parent=self)
            self.append_log(f"[{dom}] Gagal mencari rule: {msg}")
            return

        self.clear_all_rows()
        
        if rule:
            t_url = rule.get('target_url', '')
            full_dom_path = f"{dom}{path}" if path != '/root' else dom
            self.add_rule_row(domain_path=full_dom_path, target_url=t_url)
            self.append_log(f"[{dom}] Rule '{path}' DITEMUKAN! Target URL saat ini: {t_url}")
            messagebox.showinfo("Rule Ditemukan", f"Rule '{path}' ditemukan pada Cloudflare!\n\nTarget URL saat ini:\n{t_url}\n\nSilakan ubah URL tujuan pada kolom kanan lalu klik Mulai Update.", parent=self)
        else:
            full_dom_path = f"{dom}{path}" if path != '/root' else dom
            self.add_rule_row(domain_path=full_dom_path, target_url="https://")
            self.append_log(f"[{dom}] Rule '{path}' belum ada di Cloudflare. Anda bisa membuatnya sekarang.")
            messagebox.showinfo("Rule Belum Ada", f"Rule '{path}' belum ada di Cloudflare.\n\nFormulir di bawah telah disiapkan untuk membuat rule baru.", parent=self)

    def load_existing_rules_from_cf(self):
        target_domain = self.initial_domain
        if not target_domain and self.rule_rows:
            first_path = self.rule_rows[0]['path_entry'].get().strip()
            if '/' in first_path:
                target_domain = first_path.split('/', 1)[0]
            elif first_path:
                target_domain = first_path

        dialog_input = ctk.CTkInputDialog(text="Masukkan nama domain untuk memuat rules dari CF:", title="Load Rules Cloudflare")
        center_window_over_parent(dialog_input, self, 350, 200)
        domain_query = dialog_input.get_input()
        
        if not domain_query:
            return
            
        domain_query = domain_query.strip().lower()
        if domain_query.startswith("http://"): domain_query = domain_query[7:]
        if domain_query.startswith("https://"): domain_query = domain_query[8:]
        domain_query = domain_query.strip('/')

        custom_token = self.token_entry.get().strip() or None
        
        self.append_log(f"[{domain_query}] Memuat existing rules dari Cloudflare...")
        
        prof_name, api, zone_id, zone_name, ns_list, err_msg = self.resolve_api_and_zone_for_domain(domain_query, custom_token)
        if not zone_id:
            messagebox.showerror("Error", err_msg or f"Domain '{domain_query}' tidak ditemukan pada profil CF manapun.", parent=self)
            return

        success, rules_list, msg = api.fetch_existing_redirect_rules(zone_id, custom_token=custom_token)
        if not success:
            messagebox.showerror("Error", f"Gagal mengambil rules dari CF:\n{msg}", parent=self)
            self.append_log(f"[{domain_query}] Gagal load rules: {msg}")
            return

        if not rules_list:
            messagebox.showinfo("Informasi", f"Tidak ada redirect rules yang ditemukan pada domain {domain_query}.", parent=self)
            self.append_log(f"[{domain_query}] Tidak ada existing rules di Cloudflare.")
            return

        self.clear_all_rows()
        
        loaded_count = 0
        for r in rules_list:
            desc = r.get('description', '')
            t_url = r.get('target_url', '')
            if desc == "Root":
                self.root_enabled_var.set(True)
                self.root_url_entry.delete(0, "end")
                self.root_url_entry.insert(0, t_url)
            else:
                p_name = desc if desc.startswith('/') else f"/{desc}"
                full_dom_path = f"{domain_query}{p_name}"
                self.add_rule_row(domain_path=full_dom_path, target_url=t_url)
                loaded_count += 1

        self.append_log(f"[{domain_query}] Berhasil memuat {loaded_count} path rules dan Root rule dari CF!")
        messagebox.showinfo("Berhasil", f"Berhasil memuat rules untuk domain '{domain_query}'!", parent=self)

    def append_log(self, message):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", message + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def start_process(self):
        custom_token = self.token_entry.get().strip() or None
        self.config["rules_custom_token"] = custom_token or ""
        self.config["rules_selected_profile"] = self.profile_select_var.get()
        config_manager.save_config(self.config)

        root_url = self.root_url_entry.get().strip() if self.root_enabled_var.get() else None
        
        domain_rules_map = {}
        
        for r in self.rule_rows:
            path_str = r['path_entry'].get().strip()
            target_str = r['target_entry'].get().strip()
            if not path_str or not target_str:
                continue
                
            if '://' in path_str:
                path_str = path_str.split('://', 1)[1]
                
            if '/' in path_str:
                dom, p = path_str.split('/', 1)
                p = '/' + p.strip('/')
            else:
                dom = path_str
                p = '/root'
                
            dom = dom.strip()
            if dom not in domain_rules_map:
                domain_rules_map[dom] = []
            domain_rules_map[dom].append({'path': p, 'target_url': target_str})

        if not domain_rules_map and self.parent.domains_data:
            for d_item in self.parent.domains_data:
                dom = d_item.get('domain')
                if dom:
                    domain_rules_map[dom] = []

        if not domain_rules_map and not root_url:
            messagebox.showerror("Error", "Masukkan sekurang-kurangnya 1 baris rule atau aktifkan Root Rule.", parent=self)
            return

        self.btn_submit.configure(state="disabled")
        self.btn_cancel.configure(state="disabled")
        self.progress_var.set(0)
        self.append_log(f"Memulai pembuatan/update Redirect Rules untuk {len(domain_rules_map)} domain...")

        threading.Thread(
            target=self._process_rules_worker,
            args=(domain_rules_map, root_url, custom_token),
            daemon=True
        ).start()

    def _process_rules_worker(self, domain_rules_map, root_url, custom_token):
        try:
            total = len(domain_rules_map)
            completed = 0

            for domain_str, path_rules in domain_rules_map.items():
                self.append_log(f"[{domain_str}] Mencari zone di Cloudflare...")
                
                prof_name, api, zone_id, zone_name, ns_list, err_msg = self.resolve_api_and_zone_for_domain(domain_str, custom_token)
                
                if not zone_id:
                    self.append_log(f"[{domain_str}] Error: {err_msg or 'Zone tidak ditemukan pada profil CF manapun.'}")
                    completed += 1
                    self.after(0, lambda c=completed, t=total: self.progress_var.set(c / t))
                    continue

                active_token_name = "Token CF Khusus" if custom_token else f"Profil '{prof_name}'"
                self.append_log(f"[{domain_str}] Zone ditemukan ({zone_name}). Memproses rules via {active_token_name}...")

                success, msg = api.apply_redirect_rules(
                    zone_id=zone_id,
                    root_url=root_url,
                    path_rules=path_rules,
                    custom_token=custom_token
                )

                if success:
                    log_msg = f"[{domain_str}] BERHASIL: Redirect rules diperbarui."
                    if root_url:
                        log_msg += f" Root (302 -> {root_url}, Order: Last)."
                    if path_rules:
                        log_msg += f" {len(path_rules)} Path rules dibuat/diupdate (Order: First)."
                    self.append_log(log_msg)
                    app_logger.info(f"[{domain_str}] Redirect rules updated successfully.")
                else:
                    self.append_log(f"[{domain_str}] GAGAL: {msg}")
                    app_logger.error(f"[{domain_str}] Redirect rules error: {msg}")

                completed += 1
                self.after(0, lambda c=completed, t=total: self.progress_var.set(c / t))
                time.sleep(1)

            self.append_log("--- Pemrosesan Redirect Rules Selesai ---")
        except Exception as e:
            self.append_log(f"Error tidak terduga: {str(e)}")
            app_logger.error(f"Worker error: {str(e)}")
        finally:
            self.after(0, self._on_finish_rules)

    def _on_finish_rules(self):
        self.btn_submit.configure(state="normal")
        self.btn_cancel.configure(state="normal")
        self.update_idletasks()
        messagebox.showinfo("Selesai", "Pemrosesan Redirect Rules telah selesai!", parent=self)

class AddSubdomainDialog(ctk.CTkToplevel):
    def __init__(self, parent, config, domains_data, on_success_callback, prefill_domain=""):
        super().__init__(parent)
        self.parent = parent
        self.config = config
        self.domains_data = domains_data
        self.on_success_callback = on_success_callback
        
        self.title("Tambah Subdomain Baru")
        self.resizable(False, False)
        self.configure(fg_color="#202020")
        
        self.custom_font = ctk.CTkFont(family="Segoe UI", size=11)
        self.bold_font = ctk.CTkFont(family="Segoe UI", size=11, weight="bold")
        
        self.build_ui(prefill_domain)
        center_window_over_parent(self, parent, 480, 390)
        self.grab_set()
        
    def build_ui(self, prefill_domain):
        ctk.CTkLabel(self, text="Tambah Subdomain Baru", font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold")).pack(pady=(15, 10))
        
        frame = ctk.CTkFrame(self, fg_color="#282828", corner_radius=8)
        frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        
        # Subdomain / Domain Entry
        ctk.CTkLabel(frame, text="Nama Subdomain / Full Domain:", font=self.custom_font).pack(anchor="w", padx=15, pady=(10, 2))
        self.domain_entry = ctk.CTkEntry(frame, placeholder_text="contoh: sub.domain.com atau blog.domain.com", font=self.custom_font, fg_color="#1E1E1E", border_color="#444444", corner_radius=8)
        self.domain_entry.pack(fill="x", padx=15, pady=(0, 10))
        if prefill_domain:
            if not prefill_domain.startswith("sub.") and not prefill_domain.startswith("blog."):
                prefill_text = f"sub.{prefill_domain}"
            else:
                prefill_text = prefill_domain
            self.domain_entry.insert(0, prefill_text)
            
        # Target IP Entry
        ctk.CTkLabel(frame, text="Target IPv4 Address:", font=self.custom_font).pack(anchor="w", padx=15, pady=(0, 2))
        self.ip_entry = ctk.CTkEntry(frame, placeholder_text="103.xxx.xxx.xxx", font=self.custom_font, fg_color="#1E1E1E", border_color="#444444", corner_radius=8)
        self.ip_entry.pack(fill="x", padx=15, pady=(0, 10))
        
        parent_ip = self.parent.ip_entry.get().strip()
        if parent_ip and is_valid_ipv4(parent_ip):
            self.ip_entry.insert(0, parent_ip)
            
        # Checkboxes
        self.proxied_var = tk.BooleanVar(value=True)
        self.add_queue_var = tk.BooleanVar(value=True)
        
        chk_frame = ctk.CTkFrame(frame, fg_color="transparent")
        chk_frame.pack(fill="x", padx=15, pady=5)
        
        ctk.CTkCheckBox(chk_frame, text="Proxy Cloudflare (Orange Cloud)", font=self.custom_font, variable=self.proxied_var).pack(anchor="w", pady=2)
        ctk.CTkCheckBox(chk_frame, text="Tambahkan ke Daftar Domain", font=self.custom_font, variable=self.add_queue_var).pack(anchor="w", pady=2)
        
        # Status Label
        self.status_label = ctk.CTkLabel(frame, text="", font=self.custom_font, text_color="#3B82F6", wraplength=400)
        self.status_label.pack(pady=5)
        
        # Action Buttons
        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.pack(fill="x", padx=15, pady=(5, 10))
        
        self.btn_cancel = ctk.CTkButton(btn_frame, text="Batal", font=self.custom_font, width=90, fg_color="#2D2D2D", hover_color="#353535", command=self.destroy, corner_radius=8)
        self.btn_cancel.pack(side="right", padx=(5, 0))
        
        self.btn_submit = ctk.CTkButton(btn_frame, text="Cari & Buat Subdomain", font=self.bold_font, width=160, fg_color="#0284C7", hover_color="#0369A1", command=self.start_submit, corner_radius=8)
        self.btn_submit.pack(side="right")

    def start_submit(self):
        domain_str = self.domain_entry.get().strip()
        ip_str = self.ip_entry.get().strip()
        
        if not domain_str:
            messagebox.showerror("Error", "Masukkan Nama Subdomain / Domain.", parent=self)
            return
            
        if not ip_str or not is_valid_ipv4(ip_str):
            messagebox.showerror("Error", "Masukkan Target IPv4 Address yang valid.", parent=self)
            return
            
        self.btn_submit.configure(state="disabled")
        self.btn_cancel.configure(state="disabled")
        self.status_label.configure(text="Mencari zone domain di seluruh profil Cloudflare...", text_color="#3B82F6")
        
        threading.Thread(
            target=self._process_add_subdomain,
            args=(domain_str, ip_str, self.proxied_var.get(), self.add_queue_var.get()),
            daemon=True
        ).start()

    def _process_add_subdomain(self, domain_str, ip_str, proxied, add_queue):
        prof_name, api, zone_id, zone_name, ns_list, err_msg = find_zone_across_profiles(self.config, domain_str)
        
        if not zone_id:
            self.after(0, lambda: self._on_failure(err_msg or "Domain tidak ditemukan pada profil Cloudflare manapun."))
            return
            
        self.after(0, lambda: self.status_label.configure(text=f"Domain ditemukan di profil '{prof_name}'. Membuat A Record..."))
        
        success, msg = api.upsert_dns_record(zone_id, "A", domain_str, ip_str, proxied=proxied)
        
        if success:
            app_logger.info(f"[{domain_str}] Subdomain berhasil dibuat di Cloudflare (Profil: '{prof_name}') dengan IP {ip_str}.")
            
            ns_string = ", ".join(ns_list) if ns_list else ""
            if add_queue:
                existing = False
                for item in self.domains_data:
                    if item.get('domain') == domain_str:
                        item['ip'] = ip_str
                        item['status'] = 'Success'
                        if ns_string:
                            item['nameservers'] = ns_string
                        item['error'] = ''
                        existing = True
                        break
                if not existing:
                    self.domains_data.append({
                        'domain': domain_str,
                        'ip': ip_str,
                        'profile': prof_name,
                        'status': 'Success',
                        'nameservers': ns_string,
                        'error': ''
                    })
                export_utils.save_state(self.domains_data)
                self.after(0, self.on_success_callback)
                
            self.after(0, lambda: self._on_success_finish(domain_str, zone_name, prof_name, ip_str))
        else:
            app_logger.error(f"[{domain_str}] Gagal membuat subdomain: {msg}")
            self.after(0, lambda: self._on_failure(f"Gagal membuat record DNS: {msg}"))

    def _on_failure(self, message):
        self.status_label.configure(text=message, text_color="#EF4444")
        self.btn_submit.configure(state="normal")
        self.btn_cancel.configure(state="normal")
        messagebox.showwarning("Informasi / Gagal", message, parent=self)

    def _on_success_finish(self, domain_str, zone_name, prof_name, ip_str):
        messagebox.showinfo(
            "Berhasil",
            f"Subdomain Berhasil Dibuat!\n\n"
            f"Domain Zone: {zone_name}\n"
            f"Profil CF: {prof_name}\n"
            f"Subdomain: {domain_str}\n"
            f"Target IP: {ip_str}",
            parent=self.parent
        )
        self.destroy()

class CheckDomainIPDialog(ctk.CTkToplevel):
    def __init__(self, parent, config, prefill_domains=None):
        super().__init__(parent)
        self.parent = parent
        self.config = config
        self.prefill_domains = prefill_domains or []
        self.results_data = []
        self.is_checking = False

        self.title("🔍 Cek IP Domain & Akun Cloudflare")
        self.geometry("860x640")
        self.configure(fg_color="#202020")

        self.custom_font = ctk.CTkFont(family="Segoe UI", size=11)
        self.bold_font = ctk.CTkFont(family="Segoe UI", size=11, weight="bold")

        self.build_ui()
        center_window_over_parent(self, parent, 860, 640)
        self.grab_set()

        if self.prefill_domains:
            self.domains_input.insert("1.0", "\n".join(self.prefill_domains))
            self.start_check_thread()

    def build_ui(self):
        # Header Frame
        header_frame = ctk.CTkFrame(self, fg_color="#282828", corner_radius=8)
        header_frame.pack(fill="x", padx=15, pady=(15, 10))

        ctk.CTkLabel(
            header_frame,
            text="🔍 Cek IP Publik Domain & Deteksi Profil Akun Cloudflare",
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            text_color="#38BDF8"
        ).pack(anchor="w", padx=15, pady=(10, 2))

        ctk.CTkLabel(
            header_frame,
            text="Masukkan daftar domain (satu per baris) untuk mengecek IP Publik (DNS) dan mengetahui di Profil Akun CF mana domain tersebut terdaftar.",
            font=self.custom_font,
            text_color="#A0A0A0"
        ).pack(anchor="w", padx=15, pady=(0, 10))

        # Main Input & Action Frame
        input_frame = ctk.CTkFrame(self, fg_color="#282828", corner_radius=8)
        input_frame.pack(fill="x", padx=15, pady=(0, 10))

        ctk.CTkLabel(input_frame, text="Daftar Domain (Contoh: domain.com, sub.domain.com):", font=self.bold_font).pack(anchor="w", padx=15, pady=(10, 2))

        self.domains_input = ctk.CTkTextbox(input_frame, height=85, font=self.custom_font, fg_color="#1E1E1E", border_color="#444444", border_width=1, corner_radius=8)
        self.domains_input.pack(fill="x", padx=15, pady=(0, 10))

        # Action Buttons for Input
        btn_bar = ctk.CTkFrame(input_frame, fg_color="transparent")
        btn_bar.pack(fill="x", padx=15, pady=(0, 10))

        self.btn_run = ctk.CTkButton(btn_bar, text="🚀 Mulai Cek IP & Profil CF", font=self.bold_font, command=self.start_check_thread, fg_color="#7C3AED", hover_color="#6D28D9", height=32, corner_radius=8)
        self.btn_run.pack(side="left", padx=(0, 10))

        ctk.CTkButton(btn_bar, text="Hapus Text", font=self.custom_font, command=self.clear_input, fg_color="#2D2D2D", hover_color="#353535", width=90, height=32, corner_radius=8).pack(side="left")

        # Progress Frame
        prog_frame = ctk.CTkFrame(self, fg_color="transparent")
        prog_frame.pack(fill="x", padx=15, pady=(0, 5))

        self.status_lbl = ctk.CTkLabel(prog_frame, text="Siap mengecek domain.", font=self.custom_font, text_color="#38BDF8")
        self.status_lbl.pack(anchor="w", pady=(0, 2))

        self.progress_bar = ctk.CTkProgressBar(prog_frame, height=8)
        self.progress_bar.pack(fill="x")
        self.progress_bar.set(0)

        # Results Table Frame
        table_frame = ctk.CTkFrame(self, fg_color="#282828", corner_radius=8)
        table_frame.pack(fill="both", expand=True, padx=15, pady=(0, 10))

        columns = ("domain", "public_ip", "profile", "cf_dns_ip", "nameservers", "status")
        self.tree = tk.ttk.Treeview(table_frame, columns=columns, show="headings", style="CheckIP.Treeview")
        
        self.tree.heading("domain", text="Domain")
        self.tree.heading("public_ip", text="IP Publik (DNS)")
        self.tree.heading("profile", text="Akun CF (Profil)")
        self.tree.heading("cf_dns_ip", text="Target IP di CF")
        self.tree.heading("nameservers", text="Nameservers")
        self.tree.heading("status", text="Status CF")

        self.tree.column("domain", width=170, minwidth=110, stretch=True)
        self.tree.column("public_ip", width=120, minwidth=90, stretch=True)
        self.tree.column("profile", width=130, minwidth=90, stretch=True)
        self.tree.column("cf_dns_ip", width=120, minwidth=90, stretch=True)
        self.tree.column("nameservers", width=180, minwidth=100, stretch=True)
        self.tree.column("status", width=95, minwidth=70, stretch=True)

        style = tk.ttk.Style(self)
        style.theme_use("default")
        style.configure("CheckIP.Treeview", background="#202020", fieldbackground="#202020", foreground="white", borderwidth=0, font=("Segoe UI", 10), rowheight=25)
        style.map('CheckIP.Treeview', background=[('selected', '#005FB8')])
        style.configure("CheckIP.Treeview.Heading", background="#282828", foreground="white", relief="flat", font=("Segoe UI", 10, "bold"))
        
        self.tree.tag_configure("evenrow", background="#202020")
        self.tree.tag_configure("oddrow", background="#282828")
        self.tree.tag_configure("found", foreground="#34D399")
        self.tree.tag_configure("not_found", foreground="#F87171")

        self.tree.pack(side="left", fill="both", expand=True)

        scrollbar = tk.ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

        self.tree.bind("<Button-3>", self.on_right_click)
        self.tree.bind("<Double-1>", self.on_double_click)

        # Bottom Action Bar
        bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        bottom_frame.pack(fill="x", padx=15, pady=(0, 15))

        ctk.CTkButton(bottom_frame, text="📋 Copy Semua Hasil", font=self.custom_font, command=self.copy_all_results, fg_color="#2D2D2D", hover_color="#353535", width=130, height=30, corner_radius=8).pack(side="left", padx=(0, 5))
        ctk.CTkButton(bottom_frame, text="💾 Export CSV", font=self.custom_font, command=self.export_csv, fg_color="#2D2D2D", hover_color="#353535", width=110, height=30, corner_radius=8).pack(side="left", padx=5)

        ctk.CTkButton(bottom_frame, text="Tutup", font=self.custom_font, command=self.destroy, fg_color="#4B5563", hover_color="#374151", width=80, height=30, corner_radius=8).pack(side="right")

    def clear_input(self):
        self.domains_input.delete("1.0", "end")

    def start_check_thread(self):
        if self.is_checking:
            return
        
        text = self.domains_input.get("1.0", "end").strip()
        if not text:
            messagebox.showwarning("Peringatan", "Masukkan minimal satu domain untuk dicek.", parent=self)
            return

        lines = [l.strip() for l in text.split('\n') if l.strip()]
        if not lines:
            return

        self.is_checking = True
        self.btn_run.configure(state="disabled", text="⏳ Sedang Memeriksa...")
        
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.results_data.clear()

        thread = threading.Thread(target=self.worker, args=(lines,), daemon=True)
        thread.start()

    def worker(self, domains):
        total = len(domains)
        for i, dom in enumerate(domains):
            self.after(0, lambda idx=i+1, d=dom: self.status_lbl.configure(text=f"Memeriksa ({idx}/{total}): {d} ..."))
            self.after(0, lambda idx=i+1: self.progress_bar.set(idx / total))

            res = check_domain_ip_and_profile(self.config, dom)
            self.results_data.append(res)

            self.after(0, lambda r=res: self.add_result_row(r))

        self.after(0, self.finish_check)

    def add_result_row(self, res):
        tag = "found" if res.get("profile") != "Tidak Ada di Profil CF" else "not_found"
        
        self.tree.insert("", "end", values=(
            res.get("domain", ""),
            res.get("public_ip", ""),
            res.get("profile", ""),
            res.get("cf_dns_ip", ""),
            res.get("nameservers", ""),
            res.get("status", "")
        ), tags=(tag,))

    def finish_check(self):
        self.is_checking = False
        self.btn_run.configure(state="normal", text="🚀 Mulai Cek IP & Profil CF")
        found_count = sum(1 for r in self.results_data if r.get("profile") != "Tidak Ada di Profil CF")
        self.status_lbl.configure(text=f"✅ Selesai mengecek {len(self.results_data)} domain ({found_count} ditemukan di profil CF Anda).")

    def on_right_click(self, event):
        item_id = self.tree.identify_row(event.y)
        if item_id:
            self.tree.selection_set(item_id)
            values = self.tree.item(item_id, "values")
            if not values:
                return
            
            domain, public_ip, profile, cf_dns_ip, ns_string, status = values
            menu = tk.Menu(self, tearoff=0)

            if domain:
                menu.add_command(label=f"📋 Copy Domain: {domain}", command=lambda: self.copy_to_clipboard(domain))
            if public_ip:
                menu.add_command(label=f"📋 Copy IP Publik (DNS): {public_ip}", command=lambda: self.copy_to_clipboard(public_ip))
            if profile:
                menu.add_command(label=f"📋 Copy Akun CF (Profil): {profile}", command=lambda: self.copy_to_clipboard(profile))
            if cf_dns_ip:
                menu.add_command(label=f"📋 Copy Target IP di CF: {cf_dns_ip}", command=lambda: self.copy_to_clipboard(cf_dns_ip))
            if status:
                menu.add_command(label=f"📋 Copy Status CF: {status}", command=lambda: self.copy_to_clipboard(status))

            ns_list = parse_nameservers_list(ns_string)
            if ns_list:
                menu.add_separator()
                for idx, ns in enumerate(ns_list, start=1):
                    menu.add_command(label=f"📋 Copy NS {idx}: {ns}", command=lambda n=ns: self.copy_to_clipboard(n))
                if len(ns_list) > 1:
                    menu.add_command(label=f"📋 Copy Semua NS ({len(ns_list)} NS)", command=lambda: self.copy_to_clipboard(", ".join(ns_list)))

            menu.add_separator()
            menu.add_command(label="📋 Copy Seluruh Baris", command=lambda: self.copy_to_clipboard(f"Domain: {domain} | IP Publik: {public_ip} | Akun CF: {profile} | Target IP CF: {cf_dns_ip} | NS: {ns_string}"))
            menu.tk_popup(event.x_root, event.y_root)

    def on_double_click(self, event):
        item_id = self.tree.identify_row(event.y)
        if item_id:
            values = self.tree.item(item_id, "values")
            if values and values[0]:
                self.copy_to_clipboard(values[0])

    def copy_to_clipboard(self, text):
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update()

    def copy_all_results(self):
        if not self.results_data:
            return
        lines = []
        for r in self.results_data:
            lines.append(f"Domain: {r['domain']} | IP Publik: {r['public_ip']} | Akun CF: {r['profile']} | Target IP CF: {r['cf_dns_ip']} | NS: {r['nameservers']}")
        text = "\n".join(lines)
        self.copy_to_clipboard(text)
        messagebox.showinfo("Hasil Dicomot", f"Berhasil menyalin {len(self.results_data)} hasil ke clipboard.", parent=self)

    def export_csv(self):
        if not self.results_data:
            messagebox.showwarning("Peringatan", "Tidak ada hasil untuk diexport.", parent=self)
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
            title="Export Hasil Cek IP & Profil CF",
            parent=self
        )
        if file_path:
            try:
                import csv
                with open(file_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(["Domain", "IP Publik (DNS)", "Akun CF (Profil)", "Target IP di CF", "Nameservers", "Status"])
                    for r in self.results_data:
                        writer.writerow([r['domain'], r['public_ip'], r['profile'], r['cf_dns_ip'], r['nameservers'], r['status']])
                messagebox.showinfo("Sukses", f"Hasil berhasil diexport ke:\n{file_path}", parent=self)
            except Exception as e:
                messagebox.showerror("Error", f"Gagal mengexport CSV:\n{e}", parent=self)

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title(f"Cloudflare Bulk Domain Tool v{update_checker.CURRENT_VERSION}")
        self.geometry("1150x740")
        self.minsize(1024, 650)
        self.configure(fg_color="#202020")
        
        self.config = config_manager.load_config()
        self.domains_data = export_utils.load_state()
        self.queue_manager = None
        
        app_logger.set_gui_callback(self.append_log)
        
        self.build_ui()
        self.update_domains_listbox()
        
        if self.config.get("auto_check_updates", True):
            self.after(2000, self.check_updates_auto)
        
    def build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(0, weight=1)
        
        self.custom_font = ctk.CTkFont(family="Segoe UI", size=11)
        self.bold_font = ctk.CTkFont(family="Segoe UI", size=11, weight="bold")
        self.log_font = ctk.CTkFont(family="Consolas", size=10)
        
        # Left Panel (Inputs)
        left_frame = ctk.CTkFrame(self, fg_color="#282828", corner_radius=8)
        left_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        
        ctk.CTkLabel(left_frame, text="Settings", font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold")).pack(pady=(10, 5))
        
        # API Profiles
        profile_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        profile_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        self.profile_var = ctk.StringVar(value=self.config.get("current_profile", "Default"))
        
        # Ensure Default exists
        if "api_profiles" not in self.config or not self.config["api_profiles"]:
            self.config["api_profiles"] = {"Default": {"api_token": "", "global_api_key": "", "email": "", "auth_method": "token"}}
            
        profiles = list(self.config["api_profiles"].keys())
        
        self.profile_menu = ctk.CTkOptionMenu(profile_frame, variable=self.profile_var, values=profiles, command=self.on_profile_change, font=self.custom_font, corner_radius=8)
        self.profile_menu.pack(side="left", fill="x", expand=True, padx=(0, 4))
        
        btn_add_prof = ctk.CTkButton(profile_frame, text="+ Add", width=45, command=self.add_profile_dialog, font=self.custom_font, fg_color="#0284C7", hover_color="#0369A1", corner_radius=8)
        btn_add_prof.pack(side="left", padx=(0, 3))

        btn_save_prof = ctk.CTkButton(profile_frame, text="Save", width=45, command=self.save_current_config_with_msg, font=self.custom_font, fg_color="#2D2D2D", hover_color="#353535", border_width=1, border_color="#3D3D3D", text_color="#FFFFFF", corner_radius=8)
        btn_save_prof.pack(side="left", padx=(0, 3))
        
        btn_del_prof = ctk.CTkButton(profile_frame, text="Del", width=38, fg_color="#8A1A23", hover_color="#A11E29", command=self.delete_profile, font=self.custom_font, corner_radius=8)
        btn_del_prof.pack(side="left")

        # Auth Method
        self.auth_var = ctk.StringVar(value="token")
        auth_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        auth_frame.pack(fill="x", padx=10, pady=5)
        ctk.CTkRadioButton(auth_frame, text="API Token", font=self.custom_font, variable=self.auth_var, value="token", command=self.toggle_auth).pack(side="left", padx=5)
        ctk.CTkRadioButton(auth_frame, text="Global API Key", font=self.custom_font, variable=self.auth_var, value="global", command=self.toggle_auth).pack(side="left", padx=5)
        
        self.token_entry = ctk.CTkEntry(left_frame, placeholder_text="Cloudflare API Token", show="*", font=self.custom_font, fg_color="#1E1E1E", border_color="#444444", corner_radius=8)
        self.token_entry.pack(fill="x", padx=10, pady=5)
        
        self.email_entry = ctk.CTkEntry(left_frame, placeholder_text="Cloudflare Email", font=self.custom_font, fg_color="#1E1E1E", border_color="#444444", corner_radius=8)
        self.email_entry.pack(fill="x", padx=10, pady=5)
        
        self.global_key_entry = ctk.CTkEntry(left_frame, placeholder_text="Global API Key", show="*", font=self.custom_font, fg_color="#1E1E1E", border_color="#444444", corner_radius=8)
        self.global_key_entry.pack(fill="x", padx=10, pady=5)
        
        ip_batch_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        ip_batch_frame.pack(fill="x", padx=10, pady=5)
        
        ip_subframe = ctk.CTkFrame(ip_batch_frame, fg_color="transparent")
        ip_subframe.pack(side="left", fill="x", expand=True, padx=(0, 5))
        ctk.CTkLabel(ip_subframe, text="Target IPv4 Address", font=self.custom_font).pack(anchor="w", pady=(0, 2))
        self.ip_entry = ctk.CTkEntry(ip_subframe, placeholder_text="103.xxx.xxx.xxx", font=self.custom_font, fg_color="#1E1E1E", border_color="#444444", corner_radius=8)
        self.ip_entry.pack(fill="x")

        batch_subframe = ctk.CTkFrame(ip_batch_frame, fg_color="transparent", width=90)
        batch_subframe.pack(side="left", fill="x")
        ctk.CTkLabel(batch_subframe, text="Batch Size", font=self.custom_font).pack(anchor="w", pady=(0, 2))
        self.batch_entry = ctk.CTkEntry(batch_subframe, placeholder_text="10", width=80, font=self.custom_font, fg_color="#1E1E1E", border_color="#444444", corner_radius=8)
        self.batch_entry.pack(fill="x")
        self.batch_entry.insert(0, str(self.config.get("batch_size", 10)))
        
        self.on_profile_change(self.profile_var.get())
        
        ctk.CTkLabel(left_frame, text="Domains (One per line, or domain, ip)", font=self.custom_font).pack(pady=(10, 0), padx=10, anchor="w")
        self.domains_text = ctk.CTkTextbox(left_frame, height=120, font=self.custom_font, fg_color="#1E1E1E", border_color="#444444", border_width=1, corner_radius=8)
        self.domains_text.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Add domains button
        ctk.CTkButton(left_frame, text="Load Domains to Queue", font=self.bold_font, height=34, command=self.load_domains, fg_color="#2D2D2D", hover_color="#353535", border_width=1, border_color="#3D3D3D", text_color="#FFFFFF", corner_radius=8).pack(fill="x", padx=10, pady=(10, 15))
        
        # Right Panel (List and Logs)
        right_frame = ctk.CTkFrame(self, fg_color="#282828", corner_radius=8)
        right_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        right_frame.grid_rowconfigure(1, weight=2)
        right_frame.grid_rowconfigure(3, weight=1)
        right_frame.grid_columnconfigure(0, weight=1)
        
        # Controls Frame (2-Row Layout)
        controls_frame = ctk.CTkFrame(right_frame, fg_color="transparent")
        controls_frame.grid(row=0, column=0, sticky="ew", pady=(10, 5), padx=10)
        
        # Row 1: Primary Action Controls
        row1_frame = ctk.CTkFrame(controls_frame, fg_color="transparent")
        row1_frame.pack(fill="x", pady=(0, 5))
        
        self.btn_start = ctk.CTkButton(row1_frame, text="Start", font=self.bold_font, command=self.start_process, fg_color="#185C37", hover_color="#1B6C40", width=80, height=30, corner_radius=8)
        self.btn_start.pack(side="left", padx=(0, 5))
        
        self.btn_update_ip = ctk.CTkButton(row1_frame, text="Ubah IP", font=self.bold_font, command=self.start_update_ip_process, fg_color="#D97706", hover_color="#B45309", width=80, height=30, corner_radius=8)
        self.btn_update_ip.pack(side="left", padx=5)

        self.btn_add_subdomain = ctk.CTkButton(row1_frame, text="+ Subdomain", font=self.bold_font, command=lambda: self.open_add_subdomain_dialog(), fg_color="#0284C7", hover_color="#0369A1", width=100, height=30, corner_radius=8)
        self.btn_add_subdomain.pack(side="left", padx=5)

        self.btn_rules = ctk.CTkButton(row1_frame, text="⚡ CF Rules", font=self.bold_font, command=self.open_redirect_rules_dialog, fg_color="#7C3AED", hover_color="#6D28D9", width=95, height=30, corner_radius=8)
        self.btn_rules.pack(side="left", padx=5)
        
        self.btn_stop = ctk.CTkButton(row1_frame, text="Stop", font=self.bold_font, command=self.stop_process, fg_color="#8A1A23", hover_color="#A11E29", state="disabled", width=75, height=30, corner_radius=8)
        self.btn_stop.pack(side="right", padx=(5, 0))

        self.btn_resume = ctk.CTkButton(row1_frame, text="Resume", font=self.bold_font, command=self.resume_process, state="disabled", width=75, height=30, fg_color="#005FB8", hover_color="#0078D4", corner_radius=8)
        self.btn_resume.pack(side="right", padx=5)

        self.btn_pause = ctk.CTkButton(row1_frame, text="Pause", font=self.bold_font, command=self.pause_process, state="disabled", width=75, height=30, fg_color="#005FB8", hover_color="#0078D4", corner_radius=8)
        self.btn_pause.pack(side="right", padx=5)
        
        # Row 2: Queue Management & Utility Controls
        row2_frame = ctk.CTkFrame(controls_frame, fg_color="transparent")
        row2_frame.pack(fill="x")

        ctk.CTkLabel(row2_frame, text="Antrian:", font=self.custom_font, text_color="#A0A0A0").pack(side="left", padx=(0, 5))

        ctk.CTkButton(row2_frame, text="Clear Queue", font=self.custom_font, command=self.clear_queue, width=90, height=28, fg_color="#2D2D2D", hover_color="#353535", border_width=1, border_color="#3D3D3D", text_color="#FFFFFF", corner_radius=8).pack(side="left", padx=5)
        ctk.CTkButton(row2_frame, text="Hapus Selesai", font=self.custom_font, command=self.clear_done_queue, width=95, height=28, fg_color="#2D2D2D", hover_color="#353535", border_width=1, border_color="#3D3D3D", text_color="#FFFFFF", corner_radius=8).pack(side="left", padx=5)

        ctk.CTkButton(row2_frame, text="Show NS", font=self.custom_font, command=self.show_ns_summary, width=80, height=28, fg_color="#2D2D2D", hover_color="#353535", border_width=1, border_color="#3D3D3D", text_color="#FFFFFF", corner_radius=8).pack(side="right", padx=(5, 0))
        ctk.CTkButton(row2_frame, text="Export CSV", font=self.custom_font, command=self.export_csv, width=85, height=28, fg_color="#2D2D2D", hover_color="#353535", border_width=1, border_color="#3D3D3D", text_color="#FFFFFF", corner_radius=8).pack(side="right", padx=5)
        ctk.CTkButton(row2_frame, text="🔍 Cek IP & Profil CF", font=self.custom_font, command=self.open_check_ip_dialog, width=140, height=28, fg_color="#7C3AED", hover_color="#6D28D9", text_color="#FFFFFF", corner_radius=8).pack(side="right", padx=5)
        ctk.CTkButton(row2_frame, text="⚡ Cek Update", font=self.custom_font, command=self.check_updates_manual, width=95, height=28, fg_color="#10B981", hover_color="#059669", text_color="#FFFFFF", corner_radius=8).pack(side="right", padx=5)

        # Domains List (using standard Treeview for columns inside a tkinter Frame)
        list_frame = ctk.CTkFrame(right_frame)
        list_frame.grid(row=1, column=0, sticky="nsew", pady=5)
        list_frame.grid_columnconfigure(0, weight=1)
        list_frame.grid_rowconfigure(0, weight=1)
        
        columns = ("domain", "ip", "profile", "status", "nameservers", "error")
        self.tree = tk.ttk.Treeview(list_frame, columns=columns, show="headings", style="Custom.Treeview")
        self.tree.heading("domain", text="Domain")
        self.tree.heading("ip", text="Target IP")
        self.tree.heading("profile", text="Profil CF")
        self.tree.heading("status", text="Status")
        self.tree.heading("nameservers", text="Nameservers")
        self.tree.heading("error", text="Error")
        
        self.tree.column("domain", width=160, minwidth=100, stretch=True)
        self.tree.column("ip", width=110, minwidth=80, stretch=True)
        self.tree.column("profile", width=110, minwidth=80, stretch=True)
        self.tree.column("status", width=85, minwidth=65, stretch=True)
        self.tree.column("nameservers", width=180, minwidth=110, stretch=True)
        self.tree.column("error", width=150, minwidth=80, stretch=True)
        
        # A bit of styling for the treeview in dark mode
        style = tk.ttk.Style(self)
        style.theme_use("default")
        style.configure("Custom.Treeview", background="#202020", fieldbackground="#202020", foreground="white", borderwidth=0, font=("Segoe UI", 10), rowheight=25)
        style.map('Custom.Treeview', background=[('selected', '#005FB8')])
        style.configure("Custom.Treeview.Heading", background="#282828", foreground="white", relief="flat", font=("Segoe UI", 11, "bold"))
        
        self.tree.tag_configure("evenrow", background="#202020")
        self.tree.tag_configure("oddrow", background="#282828")
        
        self.tree.grid(row=0, column=0, sticky="nsew")
        
        scrollbar = tk.ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.grid(row=0, column=1, sticky="ns")

        # Progress
        self.progress_var = tk.DoubleVar()
        self.progress = ctk.CTkProgressBar(right_frame, variable=self.progress_var)
        self.progress.grid(row=2, column=0, sticky="ew", pady=10)
        self.progress.set(0)
        
        # Log Box
        self.log_text = ctk.CTkTextbox(right_frame, height=120, font=self.log_font, fg_color="#1E1E1E", border_color="#444444", border_width=1, corner_radius=8)
        self.log_text.grid(row=3, column=0, sticky="nsew", pady=(5, 10), padx=10)
        self.log_text.configure(state="disabled")
        
        # Bind right click & double click on Treeview
        self.tree.bind("<Button-3>", self.on_right_click)
        self.tree.bind("<Double-1>", self.on_double_click)

    def on_right_click(self, event):
        item_id = self.tree.identify_row(event.y)
        if item_id:
            self.tree.selection_set(item_id)
            item = self.tree.item(item_id)
            values = item['values']
            if not values:
                return

            domain = values[0] if len(values) > 0 else ""
            ip = values[1] if len(values) > 1 else ""
            profile = values[2] if len(values) > 2 else ""
            status = values[3] if len(values) > 3 else ""
            ns_string = values[4] if len(values) > 4 else ""
            error_msg = values[5] if len(values) > 5 else ""

            menu = tk.Menu(self, tearoff=0)

            # Copy Individual Fields
            if domain:
                menu.add_command(label=f"📋 Copy Domain: {domain}", command=lambda: self.copy_to_clipboard(domain))
            if ip:
                menu.add_command(label=f"📋 Copy Target IP: {ip}", command=lambda: self.copy_to_clipboard(ip))
            if profile:
                menu.add_command(label=f"📋 Copy Profil CF: {profile}", command=lambda: self.copy_to_clipboard(profile))
            if status:
                menu.add_command(label=f"📋 Copy Status: {status}", command=lambda: self.copy_to_clipboard(status))

            # Copy Nameservers (NS 1, NS 2, NS 3, NS 4, etc.)
            ns_list = parse_nameservers_list(ns_string)
            if ns_list:
                menu.add_separator()
                for idx, ns in enumerate(ns_list, start=1):
                    menu.add_command(label=f"📋 Copy NS {idx}: {ns}", command=lambda n=ns: self.copy_to_clipboard(n))
                if len(ns_list) > 1:
                    menu.add_command(label=f"📋 Copy Semua NS ({len(ns_list)} NS)", command=lambda: self.copy_to_clipboard(", ".join(ns_list)))

            # Error Message Detail
            if error_msg:
                menu.add_separator()
                menu.add_command(label="⚠️ Lihat Detail Error Lengkap...", command=lambda: self.show_error_dialog(domain, error_msg))
                menu.add_command(label="📋 Copy Message Error", command=lambda: self.copy_to_clipboard(error_msg))

            # Domain Operations / Actions
            if domain:
                menu.add_separator()
                menu.add_command(label=f"Edit Target IP untuk {domain}", command=lambda: self.edit_single_domain_ip_dialog(domain))
                menu.add_command(label=f"Edit Profil CF untuk {domain}", command=lambda: self.edit_single_domain_profile_dialog(domain))
                menu.add_command(label=f"Proses Ubah IP Cloudflare untuk {domain}", command=lambda: self.update_single_domain_dialog(domain, item_id))
                menu.add_command(label=f"Tambah Subdomain untuk {domain}", command=lambda: self.open_add_subdomain_dialog(domain))
                menu.add_command(label=f"⚡ Buat Redirect Rules untuk {domain}", command=lambda: self.open_redirect_rules_dialog_for_domain(domain))
                menu.add_command(label=f"🔍 Cek IP & Deteksi Akun CF untuk {domain}", command=lambda: self.open_check_ip_dialog(domain))
                menu.add_command(label=f"Reset Status {domain} ke Pending", command=lambda: self.reset_single_domain_status(item_id))
                menu.add_command(label=f"Hapus {domain} dari Antrian", command=lambda: self.delete_single_domain(domain))

            menu.tk_popup(event.x_root, event.y_root)

    def on_double_click(self, event):
        item_id = self.tree.identify_row(event.y)
        if item_id:
            values = self.tree.item(item_id, "values")
            if not values:
                return
            domain = values[0] if len(values) > 0 else ""
            error_msg = values[5] if len(values) > 5 else ""
            if error_msg:
                self.show_error_dialog(domain, error_msg)

    def show_error_dialog(self, domain, error_msg):
        ShowErrorDialog(self, domain, error_msg)

    def prompt_input(self, title, text):
        dialog = ctk.CTkInputDialog(text=text, title=title)
        center_window_over_parent(dialog, self, 320, 200)
        return dialog.get_input()

    def edit_single_domain_ip_dialog(self, domain):
        new_ip = self.prompt_input("Edit Target IP", f"Masukkan Target IP Baru untuk {domain}:")
        if new_ip:
            new_ip = new_ip.strip()
            if not is_valid_ipv4(new_ip):
                messagebox.showerror("Error", "IP Address tidak valid.", parent=self)
                return
            for d in self.domains_data:
                if d.get('domain') == domain:
                    d['ip'] = new_ip
                    break
            export_utils.save_state(self.domains_data)
            self.update_domains_listbox()
            app_logger.info(f"Target IP untuk '{domain}' diubah menjadi {new_ip}")

    def edit_single_domain_profile_dialog(self, domain):
        profiles = list(self.config.get("api_profiles", {}).keys())
        if not profiles:
            messagebox.showwarning("Peringatan", "Belum ada profil CF tersimpan.", parent=self)
            return

        current_prof = self.profile_var.get()
        target_item = None
        for d in self.domains_data:
            if d.get('domain') == domain:
                target_item = d
                current_prof = d.get('profile', current_prof)
                break

        dialog = ctk.CTkToplevel(self)
        dialog.title(f"Edit Profil CF - {domain}")
        dialog.resizable(False, False)
        dialog.configure(fg_color="#202020")
        center_window_over_parent(dialog, self, 350, 180)
        dialog.grab_set()

        ctk.CTkLabel(dialog, text=f"Pilih Profil CF untuk:\n{domain}", font=self.bold_font).pack(pady=(15, 10))

        selected_prof_var = ctk.StringVar(value=current_prof)
        prof_dropdown = ctk.CTkOptionMenu(dialog, variable=selected_prof_var, values=profiles, font=self.custom_font)
        prof_dropdown.pack(pady=10, padx=20, fill="x")

        def save_profile():
            new_prof = selected_prof_var.get()
            if target_item:
                target_item['profile'] = new_prof
                export_utils.save_state(self.domains_data)
                self.update_domains_listbox()
                app_logger.info(f"Profil CF untuk '{domain}' diubah menjadi '{new_prof}'.")
            dialog.destroy()

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(10, 15))
        ctk.CTkButton(btn_frame, text="Batal", width=80, command=dialog.destroy, fg_color="#2D2D2D", hover_color="#353535").pack(side="right", padx=(5, 0))
        ctk.CTkButton(btn_frame, text="Simpan", width=100, command=save_profile, fg_color="#0284C7", hover_color="#0369A1", font=self.bold_font).pack(side="right")

    def delete_single_domain(self, domain):
        self.domains_data = [d for d in self.domains_data if d.get('domain') != domain]
        export_utils.save_state(self.domains_data)
        self.update_domains_listbox()
        app_logger.info(f"Domain '{domain}' dihapus dari antrian.")

    def open_add_subdomain_dialog(self, prefill_domain=""):
        dialog = AddSubdomainDialog(
            parent=self,
            config=self.config,
            domains_data=self.domains_data,
            on_success_callback=self.update_domains_listbox,
            prefill_domain=prefill_domain
        )

    def open_check_ip_dialog(self, prefill_domain=""):
        domains = [prefill_domain] if prefill_domain else []
        dialog = CheckDomainIPDialog(parent=self, config=self.config, prefill_domains=domains)
    def open_redirect_rules_dialog(self):
        dialog = RedirectRulesDialog(parent=self, config=self.config)
        center_window_over_parent(dialog, self, 680, 640)

    def open_redirect_rules_dialog_for_domain(self, domain):
        dialog = RedirectRulesDialog(parent=self, config=self.config)
        dialog.rules_text.insert("1.0", f"{domain}/jamp, https://masuk2.klikaja.online/register\n")
        center_window_over_parent(dialog, self, 680, 640)

    def copy_to_clipboard(self, text):
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update()
        app_logger.info(f"Copied to clipboard: {text}")

    def toggle_auth(self):
        method = self.auth_var.get()
        if method == "token":
            self.email_entry.pack_forget()
            self.global_key_entry.pack_forget()
            # Need to re-insert in order if needed, but this is simple enough
            self.token_entry.pack(fill="x", padx=10, pady=5, before=self.ip_entry)
        else:
            self.token_entry.pack_forget()
            self.email_entry.pack(fill="x", padx=10, pady=5, before=self.ip_entry)
            self.global_key_entry.pack(fill="x", padx=10, pady=5, before=self.ip_entry)

    def append_log(self, msg):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")
        
    def save_current_config(self):
        profile_name = self.profile_var.get()
        if "api_profiles" not in self.config:
            self.config["api_profiles"] = {}
        if profile_name not in self.config["api_profiles"]:
            self.config["api_profiles"][profile_name] = {}
            
        prof = self.config["api_profiles"][profile_name]
        prof['auth_method'] = self.auth_var.get()
        prof['api_token'] = self.token_entry.get().strip()
        prof['email'] = self.email_entry.get().strip()
        prof['global_api_key'] = self.global_key_entry.get().strip()
        
        try:
            b_size = int(self.batch_entry.get().strip())
            self.config['batch_size'] = b_size
        except Exception:
            pass

        self.config["current_profile"] = profile_name
        config_manager.save_config(self.config)

    def on_profile_change(self, profile_name):
        if profile_name in self.config.get("api_profiles", {}):
            prof = self.config["api_profiles"][profile_name]
            
            self.auth_var.set(prof.get("auth_method", "token"))
            
            self.token_entry.delete(0, "end")
            self.token_entry.insert(0, prof.get("api_token", ""))
            
            self.email_entry.delete(0, "end")
            self.email_entry.insert(0, prof.get("email", ""))
            
            self.global_key_entry.delete(0, "end")
            self.global_key_entry.insert(0, prof.get("global_api_key", ""))
            
            self.toggle_auth()
            self.config["current_profile"] = profile_name
            config_manager.save_config(self.config)

    def add_profile_dialog(self):
        def on_profile_created(new_name):
            profiles = list(self.config.get("api_profiles", {}).keys())
            self.profile_menu.configure(values=profiles)
            self.profile_menu.set(new_name)
            self.profile_var.set(new_name)
            self.on_profile_change(new_name)
            
        dialog = AddProfileDialog(self, self.config, on_profile_created)

    def save_current_config_with_msg(self):
        self.save_current_config()
        prof_name = self.profile_var.get()
        app_logger.info(f"Pengaturan profil '{prof_name}' berhasil disimpan.")
        messagebox.showinfo("Tersimpan", f"Pengaturan profil '{prof_name}' berhasil disimpan.", parent=self)

    def save_profile_dialog(self):
        name = self.prompt_input("Save Profile", "Enter new profile name:")
        if name:
            name = name.strip()
            if name:
                self.profile_var.set(name)
                self.save_current_config()
                
                # Update dropdown options
                profiles = list(self.config["api_profiles"].keys())
                self.profile_menu.configure(values=profiles)
                self.profile_menu.set(name)
                app_logger.info(f"Profile '{name}' saved.")

    def delete_profile(self):
        name = self.profile_var.get()
        if name == "Default":
            messagebox.showwarning("Warning", "Cannot delete 'Default' profile.", parent=self)
            return
            
        if messagebox.askyesno("Confirm", f"Are you sure you want to delete profile '{name}'?", parent=self):
            if name in self.config["api_profiles"]:
                del self.config["api_profiles"][name]
                
                profiles = list(self.config["api_profiles"].keys())
                self.profile_menu.configure(values=profiles)
                
                self.profile_var.set("Default")
                self.profile_menu.set("Default")
                self.on_profile_change("Default")
                app_logger.info(f"Profile '{name}' deleted.")

    def _parse_domain_line(self, line, default_ip):
        line = line.strip()
        if not line:
            return None, None, None
            
        profiles = list(self.config.get("api_profiles", {}).keys())
        
        parts = []
        for delim in [',', '|', ';', '\t']:
            if delim in line:
                parts = [p.strip() for p in line.split(delim) if p.strip()]
                break
        if not parts:
            parts = [p.strip() for p in line.split() if p.strip()]

        if not parts:
            return None, None, None

        dom = parts[0]
        ip_cand = None
        prof_cand = None

        for p in parts[1:]:
            if is_valid_ipv4(p):
                ip_cand = p
            elif p in profiles:
                prof_cand = p

        if is_valid_ipv4(dom):
            if len(parts) > 1 and not is_valid_ipv4(parts[1]):
                dom, ip_cand = parts[1], dom

        target_ip = ip_cand if ip_cand else default_ip
        target_prof = prof_cand if prof_cand else self.profile_var.get()

        return dom, target_ip, target_prof

    def load_domains(self):
        text = self.domains_text.get("1.0", "end").strip()
        if not text:
            return
            
        default_ip = self.ip_entry.get().strip()
        current_active_profile = self.profile_var.get()
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        existing_map = {d['domain']: d for d in self.domains_data}
        
        added = 0
        updated = 0
        invalid_ip_lines = []
        
        for line in lines:
            domain, ip, prof = self._parse_domain_line(line, default_ip)
            if not domain:
                continue
                
            if ip and not is_valid_ipv4(ip):
                invalid_ip_lines.append(f"{domain} ({ip})")
                continue
                
            target_profile = prof if prof else current_active_profile

            if domain in existing_map:
                existing_map[domain]['status'] = 'Pending'
                existing_map[domain]['error'] = ''
                if ip:
                    existing_map[domain]['ip'] = ip
                if target_profile:
                    existing_map[domain]['profile'] = target_profile
                updated += 1
            else:
                self.domains_data.append({
                    'domain': domain,
                    'ip': ip if ip else "",
                    'profile': target_profile,
                    'status': 'Pending',
                    'nameservers': '',
                    'error': ''
                })
                added += 1
                
        if added > 0 or updated > 0:
            export_utils.save_state(self.domains_data)
            self.update_domains_listbox()
            self.domains_text.delete("1.0", "end")
            msg = f"Berhasil memuat antrian: {added} domain baru ditambahkan"
            if updated > 0:
                msg += f", {updated} IP/Profil domain diperbarui"
            msg += f". (Total antrian: {len(self.domains_data)})"
            app_logger.info(msg)
            
        if invalid_ip_lines:
            messagebox.showwarning(
                "Peringatan Format IP", 
                f"Beberapa baris memiliki format IP yang tidak valid dan dilewati:\n" + "\n".join(invalid_ip_lines[:10]),
                parent=self
            )

    def update_domains_listbox(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        success_count = 0
        total = len(self.domains_data)
        
        for i, item in enumerate(self.domains_data):
            tag = "evenrow" if i % 2 == 0 else "oddrow"
            profile_val = item.get('profile') or self.profile_var.get()
            self.tree.insert("", "end", values=(
                item.get('domain', ''), 
                item.get('ip', ''),
                profile_val,
                item.get('status', 'Pending'), 
                item.get('nameservers', ''), 
                item.get('error', '')
            ), tags=(tag,))
            if item.get('status') == 'Success':
                success_count += 1
                
        if total > 0:
            self.progress.set(success_count / total)
        else:
            self.progress.set(0)

    def refresh_ui_from_thread(self):
        # Update progress and listbox from main thread safely
        self.after(0, self.update_domains_listbox)
        
        # Check if running to update buttons
        if self.queue_manager and not self.queue_manager.is_running:
            self.after(0, self._set_stopped_state)

    def _set_stopped_state(self):
        self.btn_start.configure(state="normal")
        self.btn_update_ip.configure(state="normal")
        self.btn_add_subdomain.configure(state="normal")
        self.btn_pause.configure(state="disabled")
        self.btn_resume.configure(state="disabled")
        self.btn_stop.configure(state="disabled")

    def start_process(self):
        ip = self.ip_entry.get().strip()
        if not self.domains_data:
            messagebox.showerror("Error", "Queue is empty. Load domains first.")
            return
            
        missing_ip_count = sum(1 for d in self.domains_data if not d.get('ip'))
        if missing_ip_count > 0:
            if ip and is_valid_ipv4(ip):
                for d in self.domains_data:
                    if not d.get('ip'):
                        d['ip'] = ip
                export_utils.save_state(self.domains_data)
                self.update_domains_listbox()
            else:
                messagebox.showerror("Error", f"Ada {missing_ip_count} domain tanpa Target IP di antrian. Masukkan Target IPv4 Address yang valid terlebih dahulu.")
                return
                
        self.save_current_config()
        
        self.btn_start.configure(state="disabled")
        self.btn_update_ip.configure(state="disabled")
        self.btn_add_subdomain.configure(state="disabled")
        self.btn_pause.configure(state="normal")
        self.btn_stop.configure(state="normal")
        
        self.queue_manager = QueueManager(
            config=self.config,
            domains=self.domains_data,
            ip_address=ip,
            update_gui_callback=self.refresh_ui_from_thread,
            mode="point"
        )
        self.queue_manager.start()

    def start_update_ip_process(self):
        ip = self.ip_entry.get().strip()
        if not self.domains_data:
            messagebox.showerror("Error", "Queue is empty. Load domains first.")
            return

        if ip and is_valid_ipv4(ip):
            ans = messagebox.askyesnocancel(
                "Konfirmasi Ubah IP",
                f"Apakah Anda ingin memperbarui Target IP seluruh {len(self.domains_data)} domain di antrian ke IP '{ip}'?\n\n"
                f"• Klik 'Ya' untuk set seluruh domain ke IP {ip} dan jalankan update.\n"
                f"• Klik 'Tidak' untuk jalankan update menggunakan Target IP masing-masing domain di antrian.\n"
                f"• Klik 'Batal' untuk membatalkan."
            )
            if ans is None:
                return
            if ans is True:
                for d in self.domains_data:
                    d['ip'] = ip
                export_utils.save_state(self.domains_data)
                self.update_domains_listbox()
        else:
            missing_ip_count = sum(1 for d in self.domains_data if not d.get('ip'))
            if missing_ip_count > 0:
                messagebox.showerror("Error", "Masukkan Target IPv4 Address yang valid terlebih dahulu.")
                return
            if not messagebox.askyesno("Konfirmasi Ubah IP", f"Jalankan Ubah IP untuk {len(self.domains_data)} domain di antrian berdasarkan Target IP masing-masing?"):
                return

        self.save_current_config()
        
        self.btn_start.configure(state="disabled")
        self.btn_update_ip.configure(state="disabled")
        self.btn_add_subdomain.configure(state="disabled")
        self.btn_pause.configure(state="normal")
        self.btn_stop.configure(state="normal")
        
        self.queue_manager = QueueManager(
            config=self.config,
            domains=self.domains_data,
            ip_address=ip,
            update_gui_callback=self.refresh_ui_from_thread,
            mode="update_ip"
        )
        self.queue_manager.start()

    def update_single_domain_dialog(self, domain, item_id):
        new_ip = self.prompt_input("Ubah IP Domain", f"Masukkan IP Baru untuk {domain}:")
        if new_ip:
            new_ip = new_ip.strip()
            if not is_valid_ipv4(new_ip):
                messagebox.showerror("Error", "IP Address tidak valid.", parent=self)
                return
            
            threading.Thread(target=self._run_single_ip_update, args=(domain, new_ip), daemon=True).start()

    def _run_single_ip_update(self, domain, new_ip):
        app_logger.info(f"Updating IP for {domain} to {new_ip}...")
        
        target_prof = self.profile_var.get()
        target_item = None
        for item in self.domains_data:
            if item.get('domain') == domain:
                target_item = item
                if item.get('profile'):
                    target_prof = item['profile']
                break
                
        api = CloudflareAPI(self.config, profile_name=target_prof)
        success, ns, msg = api.update_domain_ip(domain, new_ip)
        
        if target_item:
            target_item['ip'] = new_ip
            if success:
                target_item['status'] = 'Success'
                if ns:
                    target_item['nameservers'] = ", ".join(ns)
                target_item['error'] = ''
                app_logger.info(f"[{domain}] IP successfully updated to {new_ip} via profile '{target_prof}'")
            else:
                target_item['status'] = 'Failed'
                target_item['error'] = f"Update IP: {msg}"
                app_logger.error(f"[{domain}] Failed to update IP via profile '{target_prof}': {msg}")
                
        export_utils.save_state(self.domains_data)
        self.after(0, self.update_domains_listbox)

    def reset_single_domain_status(self, item_id):
        item = self.tree.item(item_id)
        domain_name = item['values'][0] if item['values'] else ""
        for d in self.domains_data:
            if d.get('domain') == domain_name:
                d['status'] = 'Pending'
                d['error'] = ''
                break
        export_utils.save_state(self.domains_data)
        self.update_domains_listbox()
        app_logger.info(f"Status domain '{domain_name}' direset ke Pending.")

    def pause_process(self):
        if self.queue_manager:
            self.queue_manager.pause()
            self.btn_pause.configure(state="disabled")
            self.btn_resume.configure(state="normal")

    def resume_process(self):
        if self.queue_manager:
            self.queue_manager.resume()
            self.btn_resume.configure(state="disabled")
            self.btn_pause.configure(state="normal")

    def stop_process(self):
        if self.queue_manager:
            self.queue_manager.stop()
            self.btn_pause.configure(state="disabled")
            self.btn_resume.configure(state="disabled")
            # Start button re-enabled by the callback when thread finishes

    def clear_queue(self):
        if messagebox.askyesno("Confirm", "Are you sure you want to clear the queue and state?", parent=self):
            self.domains_data = []
            export_utils.clear_state()
            self.update_domains_listbox()
            app_logger.info("Queue cleared.")

    def clear_done_queue(self):
        done_items = [d for d in self.domains_data if d.get('status') == 'Success']
        if not done_items:
            messagebox.showinfo("Info", "Tidak ada domain berstatus 'Success' di antrian.", parent=self)
            return
            
        if messagebox.askyesno("Konfirmasi", f"Apakah Anda yakin ingin menghapus {len(done_items)} domain yang sudah sukses dari antrian?", parent=self):
            self.domains_data = [d for d in self.domains_data if d.get('status') != 'Success']
            export_utils.save_state(self.domains_data)
            self.update_domains_listbox()
            app_logger.info(f"{len(done_items)} domain berstatus Success telah dihapus dari antrian.")

    def export_csv(self):
        if not self.domains_data:
            messagebox.showwarning("Warning", "No data to export.", parent=self)
            return
            
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv")],
            initialfile="cloudflare_export.csv",
            parent=self
        )
        if filename:
            if export_utils.export_to_csv(self.domains_data, filename):
                messagebox.showinfo("Success", f"Exported to {filename}", parent=self)

    def show_ns_summary(self):
        # Group domains by nameserver
        summary = {}
        for item in self.domains_data:
            if item.get('status') == 'Success' and item.get('nameservers'):
                ns = item['nameservers']
                if ns not in summary:
                    summary[ns] = []
                summary[ns].append(item['domain'])
                
        if not summary:
            messagebox.showinfo("NS Summary", "No successfully processed domains with nameservers found.", parent=self)
            return
            
        # Create a new top level window
        top = ctk.CTkToplevel(self)
        top.title("Nameserver Summary")
        top.geometry("600x500")
        center_window_over_parent(top, self, 600, 500)
        
        textbox = ctk.CTkTextbox(top)
        textbox.pack(fill="both", expand=True, padx=10, pady=10)
        
        report = []
        for ns, domains in summary.items():
            report.append(f"Nameservers: {ns} ({len(domains)} domains)")
            for d in domains:
                report.append(f"  - {d}")
            report.append("")
            
        textbox.insert("1.0", "\n".join(report))
        textbox.configure(state="disabled")

    def check_updates_auto(self):
        update_url = self.config.get("update_url", "")
        if update_url:
            update_checker.check_for_updates(self, current_version=update_checker.CURRENT_VERSION, update_url=update_url, silent=True)

    def check_updates_manual(self):
        update_url = self.config.get("update_url", "")
        update_checker.check_for_updates(self, current_version=update_checker.CURRENT_VERSION, update_url=update_url, silent=False)

if __name__ == "__main__":
    app = App()
    app.mainloop()
