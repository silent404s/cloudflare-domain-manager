import os
import subprocess
import sys

def build():
    print("Building Standalone Windows Executable (.exe)...")
    
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconsole",
        "--onefile",
        "--name=Cloudflare Bulk Domain Tool",
        "--icon=app_icon.ico",
        "--distpath=../dist",
        "--workpath=../build",
        "--collect-all=customtkinter",
        "main.py"
    ]
    
    print("Executing command:", " ".join(cmd))
    result = subprocess.run(cmd)
    
    if result.returncode == 0:
        exe_path = os.path.abspath("dist/Cloudflare Bulk Domain Tool.exe")
        print("\n=======================================================")
        print("BUILD EXECUTABLE SUCCESSFUL!")
        print(f"Executable created at:\n{exe_path}")
        print("=======================================================\n")
        
        # Check if Inno Setup Compiler is installed to build the Windows Installer (.exe Setup)
        inno_paths = [
            r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
            r"C:\Program Files\Inno Setup 6\ISCC.exe"
        ]
        iscc_exe = next((p for p in inno_paths if os.path.exists(p)), None)
        if iscc_exe:
            print("Compiling Inno Setup Installer (.exe Wizard)...")
            iscc_res = subprocess.run([iscc_exe, "installer_setup.iss"])
            if iscc_res.returncode == 0:
                print("=======================================================")
                print("INSTALLER CREATED SUCCESSFULLY in Output/ folder!")
                print("=======================================================")
        else:
            print("[INFO] Inno Setup Compiler (ISCC.exe) tidak ditemukan. Gunakan Inno Setup jika ingin mengompilasi installer_setup.iss secara GUI/CLI.")
    else:
        print("\nBUILD FAILED! Check error log above.")

if __name__ == "__main__":
    build()
