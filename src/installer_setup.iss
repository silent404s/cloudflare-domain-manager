; =====================================================================
; Script Inno Setup Compiler - Cloudflare Bulk Domain Tool (v1.0.0)
; Membuat Installer Resmi (.exe Setup Wizard) untuk Windows
; =====================================================================

#define MyAppName "Cloudflare Bulk Domain Tool"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Skylark"
#define MyAppURL "https://github.com/silent404s/cloudflare-domain-manager"
#define MyAppExeName "Cloudflare Bulk Domain Tool.exe"

[Setup]
; Identifikasi Aplikasi (AppId unik untuk penanganan update/uninstall Windows)
AppId={{8E3A823B-CF10-4A9B-B823-9D1115F6E201}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; Tempat Instalasi Default
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes

; Lisensi & Icon Setup
LicenseFile=LICENSE
SetupIconFile=app_icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}

; Kompresi & Performa Installer
Compression=lzma2/max
SolidCompression=yes
OutputDir=..\Output
OutputBaseFilename=CloudflareBulkDomain_Setup_v{#MyAppVersion}
WizardStyle=modern

; Hak Akses Instalasi (Memungkinkan install tanpa butuh akun Administrator)
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; Otomatis Menutup Aplikasi Lama Jika Sedang Berjalan Saat Update
CloseApplications=yes
CloseApplicationsFilter=*.exe

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce

[Files]
; Executable Utama
Source: "..\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

; File Pendukung & Icon
Source: "app_icon.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "config.json.example"; DestDir: "{app}"; Flags: ignoreversion

; Konfigurasi Pengguna (Hanya dibuat jika BELUM ADA, agar setting/token lama pengguna tidak terhapus saat update)
Source: "config.json.example"; DestDir: "{app}"; DestName: "config.json"; Flags: onlyifdoesntexist

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\app_icon.ico"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\app_icon.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
