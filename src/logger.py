import logging
import datetime
import os

LOG_FILE = 'app.log'

class AppLogger:
    def __init__(self):
        self.logger = logging.getLogger("CloudflareBot")
        self.logger.setLevel(logging.DEBUG)
        
        # File handler
        file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        
        # Formatter
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        
        self.logger.addHandler(file_handler)
        self.gui_callback = None

    def set_gui_callback(self, callback):
        self.gui_callback = callback

    def _log(self, level, message):
        if level == logging.INFO:
            self.logger.info(message)
        elif level == logging.WARNING:
            self.logger.warning(message)
        elif level == logging.ERROR:
            self.logger.error(message)
        elif level == logging.DEBUG:
            self.logger.debug(message)
            
        if self.gui_callback:
            # Format time for GUI
            time_str = datetime.datetime.now().strftime("%H:%M:%S")
            self.gui_callback(f"[{time_str}] {message}")

    def info(self, message):
        self._log(logging.INFO, message)

    def warning(self, message):
        self._log(logging.WARNING, message)

    def error(self, message):
        self._log(logging.ERROR, message)

    def debug(self, message):
        self._log(logging.DEBUG, message)

app_logger = AppLogger()
