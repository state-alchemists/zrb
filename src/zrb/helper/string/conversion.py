import logging
import re

NON_WORD = re.compile(r'[\W]+')
NON_ALPHA_NUM = re.compile(r'[^0-9a-zA-Z]+')
LEADING_NUM = re.compile(r'^[0-9]+')
LOGGING_LEVEL_MAP = {
    'critical': logging.CRITICAL,
    'fatal': logging.FATAL,
    'error': logging.ERROR,
    'warning': logging.WARNING,
    'warn': logging.WARN,
    'info': logging.INFO,
    'debug': logging.DEBUG,
    'notset': logging.NOTSET,
}


def to_cmd_name(name: str) -> str:
    return NON_WORD.sub('-', name).strip('-').lower()


def to_variable_name(string: str) -> str:
    # Remove any non-alphanumeric characters
    string = NON_ALPHA_NUM.sub(' ', string).strip()
    # Convert to lowercase
    string = string.lower()
    # Replace spaces with underscores
    string = string.replace(' ', '_')
    # Remove leading digits
    string = LEADING_NUM.sub('', string)
    return string


def to_boolean(string: str) -> bool:
    if string.lower() in ['true', '1', 'yes', 'y', 'active']:
        return True
    if string.lower() in ['false', '0', 'no', 'n', 'inactive']:
        return False
    raise Exception(f'Cannot infer boolean value from "{string}"')


def to_logging_level(logging_level_str: str) -> int:
    lower_logging_level_str = logging_level_str.lower()
    if lower_logging_level_str in LOGGING_LEVEL_MAP:
        return LOGGING_LEVEL_MAP[lower_logging_level_str]
    return logging.WARNING
