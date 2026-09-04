import json
import os

CONFIG_FILE = 'config.json'

DEFAULT_CONFIG = {
    "api_profiles": {
        "Default": {
            "api_token": "",
            "global_api_key": "",
            "email": "",
            "auth_method": "token"
        }
    },
    "current_profile": "Default",
    "batch_size": 10,
    "delay_between_requests": [2, 5],
    "delay_between_batches": [30, 60],
    "max_retries": 3,
    "timeout": 30,
    "auto_check_updates": True,
    "update_url": "https://raw.githubusercontent.com/silent404s/cloudflare-domain-manager/main/version.json"
}

def load_config():
    if not os.path.exists(CONFIG_FILE):
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG
    
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            
            # Migration logic
            if "api_profiles" not in config:
                config["api_profiles"] = {
                    "Default": {
                        "api_token": config.get("api_token", ""),
                        "global_api_key": config.get("global_api_key", ""),
                        "email": config.get("email", ""),
                        "auth_method": config.get("auth_method", "token")
                    }
                }
                config["current_profile"] = "Default"
                
                # Cleanup old keys
                for k in ["api_token", "global_api_key", "email", "auth_method"]:
                    if k in config:
                        del config[k]
                
                save_config(config)

            # Auto-migrate obsolete update_url to the new repository
            if "skylark/cloudflare-bulk-domain-tool" in config.get("update_url", ""):
                config["update_url"] = DEFAULT_CONFIG["update_url"]
                save_config(config)

            # Merge with default to ensure all keys exist
            merged_config = DEFAULT_CONFIG.copy()
            merged_config.update(config)
            return merged_config
    except Exception as e:
        print(f"Error loading config: {e}")
        return DEFAULT_CONFIG

def save_config(config):
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
        return True
    except Exception as e:
        print(f"Error saving config: {e}")
        return False
