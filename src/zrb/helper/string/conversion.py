import re


def to_cmd_name(name: str) -> str:
    return re.sub(r'[\W]+', '-', name).strip('-').lower()


def to_variable_name(string):
    # Remove any non-alphanumeric characters
    string = re.sub(r'[^0-9a-zA-Z]+', ' ', string).strip()
    # Convert to lowercase
    string = string.lower()
    # Replace spaces with underscores
    string = string.replace(' ', '_')
    # Remove leading digits
    string = re.sub(r'^[0-9]+', '', string)
    return string
