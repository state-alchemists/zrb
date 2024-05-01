import keyword
import logging
import re

from zrb.helper.string.constant import FALSE_STRS, TRUE_STRS

NON_WORD = re.compile(r"[\W]+")
LEADING_NUM = re.compile(r"^\d+")
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


def untyped_to_cli_name(name: str) -> str:
    return NON_WORD.sub("-", name).strip("-").lower()


def untyped_to_variable_name(string: str) -> str:
    # Replace any non-word characters with underscore
    string = NON_WORD.sub("_", string).strip()
    # Remove leading digits
    string = LEADING_NUM.sub("", string)
    # Convert to lowercase
    string = string.lower()
    if keyword.iskeyword(string):
        return string + "_"
    return string


def untyped_to_boolean(string: str) -> bool:
    if string.lower() in TRUE_STRS:
        return True
    if string.lower() in FALSE_STRS:
        return False
    raise Exception(f'Cannot infer boolean value from "{string}"')


def untyped_to_logging_level(logging_level_str: str) -> int:
    lower_logging_level_str = logging_level_str.lower()
    if lower_logging_level_str in LOGGING_LEVEL_MAP:
        return LOGGING_LEVEL_MAP[lower_logging_level_str]
    return logging.WARNING
