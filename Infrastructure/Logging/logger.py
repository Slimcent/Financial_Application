import logging
import colorlog

# log handler for console output
console_handler = logging.StreamHandler()

# Define log format with colors
formatter = colorlog.ColoredFormatter(
    "%(log_color)s%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    log_colors={
        "DEBUG": "cyan",
        "INFO": "green",
        "WARNING": "yellow",
        "ERROR": "red",
        "CRITICAL": "bold_red"
    }
)

# Applying formatter to the handler
console_handler.setFormatter(formatter)

# Creating and configuring the logger
logger = logging.getLogger(__name__)
logger.addHandler(console_handler)
logger.setLevel(logging.DEBUG)
