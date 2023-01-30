import re


def get_cmd_name(name: str) -> str:
    return re.sub(r'[\W]+', '-', name).strip('-').lower()
