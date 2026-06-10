from datetime import datetime
from config import LOG_LEVEL

# Print log message
def log(level, msg):
    log_levels = {"DEBUG": 1, "INFO": 2, "WARNING": 3, "ERROR": 4}
    level_color_codes = {
        "DEBUG": "\033[94m",
        "INFO": "\033[92m",
        "WARNING": "\033[93m",
        "ERROR": "\033[91m"
    }
    timestamp_color_code = "\033[96m"
    reset_color_code = "\033[0m"
    if log_levels.get(level, 2) >= log_levels.get(LOG_LEVEL, 2):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        level_space = " " * (8 - len(level))
        print(f"{timestamp_color_code}[{timestamp}] {level_color_codes[level]}[{level}]{reset_color_code}{level_space}{msg}")


# Print debug log message
def debug(msg):
    log("DEBUG", msg)


# Print info log message
def info(msg):
    log("INFO", msg)


# Print warning log message
def warning(msg):
    log("WARNING", msg)


# Print error log message
def error(msg):
    log("ERROR", msg)
