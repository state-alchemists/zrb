from .util.string.conversion import to_boolean

import importlib.metadata as metadata
import logging
import os


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


def _get_log_level(level: str) -> int:
    level = level.upper()
    log_levels = {
        "CRITICAL": logging.CRITICAL,  # 50
        "ERROR": logging.ERROR,        # 40
        "WARN": logging.WARNING,       # 30
        "WARNING": logging.WARNING,    # 30
        "INFO": logging.INFO,          # 20
        "DEBUG": logging.DEBUG,        # 10
        "NOTSET": logging.NOTSET       # 0
    }
    if level in log_levels:
        return log_levels[level]
    return logging.WARNING


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
LOGGING_LEVEL = _get_log_level(os.getenv("ZRB_LOGGING_LEVEL", "WARNING"))
SHOULD_LOAD_BUILTIN = to_boolean(os.getenv("ZRB_SHOULD_LOAD_BUILTIN", "1"))
ENV_PREFIX = os.getenv("ZRB_ENV", "")
SHOW_ADVERTISEMENT = to_boolean(os.getenv("ZRB_SHOW_ADVERTISEMENT", "1"))
SHOW_PROMPT = to_boolean(os.getenv("ZRB_SHOW_PROMPT", "1"))
SHOW_TIME = to_boolean(os.getenv("ZRB_SHOW_TIME", "1"))
HTTP_PORT = int(os.getenv("ZRB_HTTP_PORT", "21213"))
VERSION = _get_version()

BANNER = f"""
                bb
   zzzzz rr rr  bb
     zz  rrr  r bbbbbb
    zz   rr     bb   bb
   zzzzz rr     bbbbbb   {VERSION} Janggala
   _ _ . .  . _ .  _ . . .

A Framework to Enhanche Your Workflow

☕ Donate at: https://stalchmst.com/donation
🐙 Submit issues/PR at: https://github.com/state-alchemists/zrb
🐤 Follow us at: https://twitter.com/zarubastalchmst
"""
