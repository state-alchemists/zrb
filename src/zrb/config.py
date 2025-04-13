import importlib.metadata as metadata
import logging
import os
import platform

from zrb.util.string.conversion import to_boolean


def _get_current_shell() -> str:
    if platform.system() == "Windows":
        return "PowerShell"
    current_shell = os.getenv("SHELL", "")
    if current_shell.endswith("zsh"):
        return "zsh"
    return "bash"


def _get_log_level(level: str) -> int:
    level = level.upper()
    log_levels = {
        "CRITICAL": logging.CRITICAL,  # 50
        "ERROR": logging.ERROR,  # 40
        "WARN": logging.WARNING,  # 30
        "WARNING": logging.WARNING,  # 30
        "INFO": logging.INFO,  # 20
        "DEBUG": logging.DEBUG,  # 10
        "NOTSET": logging.NOTSET,  # 0
    }
    if level in log_levels:
        return log_levels[level]
    return logging.WARNING


LOGGER = logging.getLogger()
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
LOAD_BUILTIN = to_boolean(os.getenv("ZRB_LOAD_BUILTIN", "1"))
WARN_UNRECOMMENDED_COMMAND = to_boolean(
    os.getenv("ZRB_WARN_UNRECOMMENDED_COMMAND", "1")
)
SESSION_LOG_DIR = os.getenv(
    "ZRB_SESSION_LOG_DIR", os.path.expanduser(os.path.join("~", ".zrb-session"))
)
TODO_DIR = os.getenv("ZRB_TODO_DIR", os.path.expanduser(os.path.join("~", "todo")))
TODO_VISUAL_FILTER = os.getenv("ZRB_TODO_FILTER", "")
TODO_RETENTION = os.getenv("ZRB_TODO_RETENTION", "2w")
VERSION = metadata.version("zrb")
WEB_HTTP_PORT = int(os.getenv("ZRB_WEB_HTTP_PORT", "21213"))
WEB_GUEST_USERNAME = os.getenv("ZRB_WEB_GUEST_USERNAME", "user")
WEB_SUPER_ADMIN_USERNAME = os.getenv("ZRB_WEB_SUPERADMIN_USERNAME", "admin")
WEB_SUPER_ADMIN_PASSWORD = os.getenv("ZRB_WEB_SUPERADMIN_PASSWORD", "admin")
WEB_ACCESS_TOKEN_COOKIE_NAME = os.getenv(
    "ZRB_WEB_ACCESS_TOKEN_COOKIE_NAME", "access_token"
)
WEB_REFRESH_TOKEN_COOKIE_NAME = os.getenv(
    "ZRB_WEB_REFRESH_TOKEN_COOKIE_NAME", "refresh_token"
)
WEB_SECRET_KEY = os.getenv("ZRB_WEB_SECRET", "zrb")
WEB_ENABLE_AUTH = to_boolean(os.getenv("ZRB_WEB_ENABLE_AUTH", "0"))
WEB_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.getenv("ZRB_WEB_ACCESS_TOKEN_EXPIRE_MINUTES", "30")
)
WEB_AUTH_REFRESH_TOKEN_EXPIRE_MINUTES = int(
    os.getenv("ZRB_WEB_REFRESH_TOKEN_EXPIRE_MINUTES", "60")
)

LLM_HISTORY_DIR = os.getenv(
    "ZRB_LLM_HISTORY_DIR", os.path.expanduser(os.path.join("~", ".zrb-llm-history"))
)
LLM_HISTORY_FILE = os.getenv(
    "ZRB_LLM_HISTORY_FILE", os.path.join(LLM_HISTORY_DIR, "history.json")
)
LLM_ALLOW_ACCESS_LOCAL_FILE = to_boolean(os.getenv("ZRB_LLM_ACCESS_LOCAL_FILE", "1"))
LLM_ALLOW_ACCESS_SHELL = to_boolean(os.getenv("ZRB_LLM_ACCESS_SHELL", "1"))
LLM_ALLOW_ACCESS_INTERNET = to_boolean(os.getenv("ZRB_LLM_ACCESS_INTERNET", "1"))
# RAG Configuration
RAG_EMBEDDING_API_KEY = os.getenv("ZRB_RAG_EMBEDDING_API_KEY", None)
RAG_EMBEDDING_BASE_URL = os.getenv("ZRB_RAG_EMBEDDING_BASE_URL", None)
RAG_EMBEDDING_MODEL = os.getenv("ZRB_RAG_EMBEDDING_MODEL", "text-embedding-ada-002")
RAG_CHUNK_SIZE = int(os.getenv("ZRB_RAG_CHUNK_SIZE", "1024"))
RAG_OVERLAP = int(os.getenv("ZRB_RAG_OVERLAP", "128"))
RAG_MAX_RESULT_COUNT = int(os.getenv("ZRB_RAG_MAX_RESULT_COUNT", "5"))
SERP_API_KEY = os.getenv("SERP_API_KEY", "")


BANNER = f"""
                bb
   zzzzz rr rr  bb
     zz  rrr  r bbbbbb
    zz   rr     bb   bb
   zzzzz rr     bbbbbb   {VERSION} Janggala
   _ _ . .  . _ .  _ . . .

Your Automation Powerhouse

☕ Donate at: https://stalchmst.com/donation
🐙 Submit issues/PR at: https://github.com/state-alchemists/zrb
🐤 Follow us at: https://twitter.com/zarubastalchmst
"""
