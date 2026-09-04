import os
import shutil
import zipfile

def make_fresh_package():
    base_dir = r"c:\Users\skylark\Downloads\pointerdomain"
    fresh_dir = os.path.join(base_dir, "Cloudflare_Bulk_Domain_Tool_Fresh")
    zip_path = os.path.join(base_dir, "Cloudflare_Bulk_Domain_Tool_Fresh.zip")
    
    if os.path.exists(fresh_dir):
        shutil.rmtree(fresh_dir)
        
    os.makedirs(fresh_dir, exist_ok=True)
    os.makedirs(os.path.join(fresh_dir, "data"), exist_ok=True)
    
    files_to_copy = [
        "main.py",
        "cloudflare_api.py",
        "config_manager.py",
        "export_utils.py",
        "logger.py",
        "queue_manager.py",
        "update_checker.py",
        "build_exe.py",
        "create_icon.py",
        "app_icon.ico",
        "installer_setup.iss",
        "version.json",
        "requirements.txt",
        "README.md",
        "LICENSE",
        "Launch_App.vbs",
        "config.json.example"
    ]
    
    for fname in files_to_copy:
        src = os.path.join(base_dir, fname)
        dst = os.path.join(fresh_dir, fname)
        if os.path.exists(src):
            shutil.copy2(src, dst)
            
    # Copy clean config.json.example as config.json (no private API tokens)
    clean_config_src = os.path.join(base_dir, "config.json.example")
    clean_config_dst = os.path.join(fresh_dir, "config.json")
    if os.path.exists(clean_config_src):
        shutil.copy2(clean_config_src, clean_config_dst)
        
    print(f"Created fresh folder at: {fresh_dir}")
    
    # Create ZIP file
    if os.path.exists(zip_path):
        os.remove(zip_path)
        
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(fresh_dir):
            for file in files:
                abs_path = os.path.join(root, file)
                rel_path = os.path.relpath(abs_path, fresh_dir)
                zipf.write(abs_path, rel_path)
                
    print(f"Created fresh ZIP package at: {zip_path}")

if __name__ == "__main__":
    make_fresh_package()
