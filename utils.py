import re
import sys

import loguru
import pycountry


def configure_logger():
    logger = loguru.logger
    logger.configure(
        handlers=[
            {
                "sink": sys.stdout,
                "format": "[<green>{time:YYYY-MM-DD HH:mm:ss}</green>]| <level>{message}</level>",
                "level": "TRACE",
                "colorize": True,
                "backtrace": True,
            }
        ]
    )
    return logger


def convert_camel_to_snake(cc_str):
    return re.sub(r"(?<!^)(?=[A-Z])", "_", cc_str).lower()


def convert_price_string(price_string):
    try:
        suffixes = {"K": 1000, "M": 1000000}
        suffix = price_string[-1]
        if suffix in suffixes:
            value = float(price_string[:-1].strip("€"))
            return int(value * suffixes[suffix])
    except:
        return None
    

def get_country_code(name):
    country = pycountry.countries.get(name=name)
    if country:
        return country.alpha_3
    
    return name[0:3].upper()