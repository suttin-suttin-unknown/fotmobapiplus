import re
import sys

from loguru import logger

logger.configure(
    handlers=[
        {
            "sink": sys.stdout,
            "format": "[<green>{time:YYYY-MM-DD HH:mm:ss}</green>] | <level>{level: <8}: {message}</level>",
            "level": "TRACE",
            "colorize": True,
            "backtrace": True,
        }
    ]
)

def convert_camel_to_snake(cc_str):
    return re.sub(r"(?<!^)(?=[A-Z])", "_", cc_str).lower()
