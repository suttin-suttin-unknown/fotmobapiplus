import re

def convert_camel_to_snake(cc_str):
    return re.sub(r"(?<!^)(?=[A-Z])", "_", cc_str).lower()