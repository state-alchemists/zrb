import importlib.metadata as metadata
import os

from zrb.helper.string.untyped_conversion import (
    untyped_to_boolean,
    untyped_to_logging_level,
)


def _get_version() -> str:
    return metadata.version("zrb")


def _get_current_shell() -> str:
    current_shell = os.getenv("SHELL", "")
    if current_shell.endswith("zsh"):
        return "zsh"
    return "bash"


def _get_default_tmp_dir() -> str:
    if os.path.isdir("/tmp"):
        return "/tmp"
    return os.path.expanduser(os.path.join("~", ".tmp"))


TMP_DIR = os.getenv("ZRB_TMP_DIR", _get_default_tmp_dir())
DEFAULT_SHELL = os.getenv("ZRB_SHELL", _get_current_shell())
DEFAULT_EDITOR = os.getenv("ZRB_EDITOR", "nano")
INIT_MODULES_STR = os.getenv("ZRB_INIT_MODULES", "")
INIT_MODULES = (
    [module.strip() for module in INIT_MODULES_STR.split(":") if module.strip() != ""]
    if INIT_MODULES_STR != ""
    else []
)
INIT_SCRIPTS_STR = os.getenv("ZRB_INIT_SCRIPTS", "")
INIT_SCRIPTS = (
    [script.strip() for script in INIT_SCRIPTS_STR.split(":") if script.strip() != ""]
    if INIT_SCRIPTS_STR != ""
    else []
)
LOGGING_LEVEL = untyped_to_logging_level(os.getenv("ZRB_LOGGING_LEVEL", "WARNING"))
SHOULD_LOAD_BUILTIN = untyped_to_boolean(os.getenv("ZRB_SHOULD_LOAD_BUILTIN", "1"))
ENV_PREFIX = os.getenv("ZRB_ENV", "")
SHOW_ADVERTISEMENT = untyped_to_boolean(os.getenv("ZRB_SHOW_ADVERTISEMENT", "1"))
SHOW_PROMPT = untyped_to_boolean(os.getenv("ZRB_SHOW_PROMPT", "1"))
SHOW_TIME = untyped_to_boolean(os.getenv("ZRB_SHOW_TIME", "1"))
VERSION = _get_version()
ENABLE_TYPE_CHECKING = untyped_to_boolean(os.getenv("ZRB_ENABLE_TYPE_CHECKING", "1"))
