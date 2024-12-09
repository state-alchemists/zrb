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
SHOW_TIME = to_boolean(os.getenv("ZRB_SHOW_TIME", "1"))
WARN_UNRECOMMENDED_COMMAND = to_boolean(
    os.getenv("ZRB_WARN_UNRECOMMENDED_COMMAND", "1")
)
SESSION_LOG_DIR = os.getenv(
    "ZRB_SESSION_LOG_DIR", os.path.expanduser(os.path.join("~", ".zrb-session"))
)
TODO_DIR = os.getenv("ZRB_TODO_DIR", os.path.expanduser(os.path.join("~", "todo")))
TODO_VISUAL_FILTER = os.getenv("ZRB_TODO_FILTER", "")
VERSION = metadata.version("zrb")
WEB_HTTP_PORT = int(os.getenv("ZRB_WEB_HTTP_PORT", "21213"))
LLM_MODEL = os.getenv("ZRB_LLM_MODEL", "ollama_chat/llama3.1")
LLM_SYSTEM_PROMPT = os.getenv("ZRB_LLM_SYSTEM_PROMPT", "You are a helpful assistant")
LLM_HISTORY_FILE = os.getenv(
    "ZRB_LLM_HISTORY_FILE",
    os.path.expanduser(os.path.join("~", ".zrb-llm-history.json")),
)
LLM_ALLOW_ACCESS_SHELL = to_boolean(os.getenv("ZRB_LLM_ACCESS_FILE", "1"))
LLM_ALLOW_ACCESS_WEB = to_boolean(os.getenv("ZRB_LLM_ACCESS_WEB", "1"))
RAG_EMBEDDING_MODEL = os.getenv("ZRB_RAG_EMBEDDING_MODEL", "ollama/nomic-embed-text")
RAG_CHUNK_SIZE = int(os.getenv("ZRB_RAG_CHUNK_SIZE", "1024"))
RAG_OVERLAP = int(os.getenv("ZRB_RAG_OVERLAP", "128"))
RAG_MAX_RESULT_COUNT = int(os.getenv("ZRB_RAG_MAX_RESULT_COUNT", "5"))


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
