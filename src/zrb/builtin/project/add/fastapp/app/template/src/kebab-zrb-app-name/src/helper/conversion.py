import logging

LOGGING_LEVEL_MAP = {
    "critical": logging.CRITICAL,
    "fatal": logging.FATAL,
    "error": logging.ERROR,
    "warning": logging.WARNING,
    "warn": logging.WARN,
    "info": logging.INFO,
    "debug": logging.DEBUG,
    "notset": logging.NOTSET,
}


def str_to_boolean(value: str):
    if value.lower() in ("0", "false", "no", "n"):
        return False
    if value.lower() in ("1", "true", "yes", "y"):
        return True
    raise Exception(f'Cannot convert to boolean: "{value}"')


def str_to_logging_level(logging_level_str: str) -> int:
    lower_logging_level_str = logging_level_str.lower()
    if lower_logging_level_str in LOGGING_LEVEL_MAP:
        return LOGGING_LEVEL_MAP[lower_logging_level_str]
    return logging.WARNING
