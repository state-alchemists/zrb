import importlib.metadata as metadata
import os
from .util.string.conversion import to_boolean


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
SHOULD_LOAD_BUILTIN = to_boolean(os.getenv("ZRB_SHOULD_LOAD_BUILTIN", "1"))
ENV_PREFIX = os.getenv("ZRB_ENV", "")
SHOW_ADVERTISEMENT = to_boolean(os.getenv("ZRB_SHOW_ADVERTISEMENT", "1"))
SHOW_PROMPT = to_boolean(os.getenv("ZRB_SHOW_PROMPT", "1"))
SHOW_TIME = to_boolean(os.getenv("ZRB_SHOW_TIME", "1"))
VERSION = _get_version()
ENABLE_TYPE_CHECKING = to_boolean(os.getenv("ZRB_ENABLE_TYPE_CHECKING", "1"))
