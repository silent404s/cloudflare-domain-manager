import csv
import json
import os
from logger import app_logger

STATE_FILE = 'data/state.json'

def init_data_dir():
    if not os.path.exists('data'):
        os.makedirs('data')

def save_state(domains_data):
    init_data_dir()
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump(domains_data, f, indent=4)
    except Exception as e:
        app_logger.error(f"Failed to save state: {e}")

def load_state():
    if not os.path.exists(STATE_FILE):
        return []
    try:
        with open(STATE_FILE, 'r') as f:
            data = json.load(f)
            for item in data:
                if 'profile' not in item:
                    item['profile'] = 'Default'
            return data
    except Exception as e:
        app_logger.error(f"Failed to load state: {e}")
        return []

def clear_state():
    if os.path.exists(STATE_FILE):
        try:
            os.remove(STATE_FILE)
        except Exception as e:
            app_logger.error(f"Failed to clear state: {e}")

def export_to_csv(domains_data, filename='data/export.csv'):
    init_data_dir()
    if not domains_data:
        app_logger.warning("No data to export.")
        return False
        
    try:
        fieldnames = []
        for item in domains_data:
            for key in item.keys():
                if key not in fieldnames:
                    fieldnames.append(key)
                    
        with open(filename, 'w', newline='', encoding='utf-8') as output_file:
            dict_writer = csv.DictWriter(output_file, fieldnames=fieldnames)
            dict_writer.writeheader()
            dict_writer.writerows(domains_data)
        app_logger.info(f"Data exported successfully to {filename}")
        return True
    except Exception as e:
        app_logger.error(f"Failed to export CSV: {e}")
        return False
