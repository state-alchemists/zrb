import importlib.metadata as metadata
import logging
import os
import platform
from textwrap import dedent

from zrb.util.string.conversion import to_boolean


class Config:
    @property
    def LOGGER(self) -> logging.Logger:
        return logging.getLogger()

    @property
    def DEFAULT_SHELL(self) -> str:
        return os.getenv("ZRB_SHELL", self._get_current_shell())

    def _get_current_shell(self) -> str:
        if platform.system() == "Windows":
            return "PowerShell"
        current_shell = os.getenv("SHELL", "")
        if current_shell.endswith("zsh"):
            return "zsh"
        return "bash"

    @property
    def DEFAULT_EDITOR(self) -> str:
        return os.getenv("ZRB_EDITOR", "nano")

    @property
    def INIT_MODULES(self) -> list[str]:
        init_modules_str = os.getenv("ZRB_INIT_MODULES", "")
        return (
            [
                module.strip()
                for module in init_modules_str.split(":")
                if module.strip() != ""
            ]
            if init_modules_str != ""
            else []
        )

    @property
    def INIT_SCRIPTS(self) -> list[str]:
        init_scripts_str = os.getenv("ZRB_INIT_SCRIPTS", "")
        return (
            [
                script.strip()
                for script in init_scripts_str.split(":")
                if script.strip() != ""
            ]
            if init_scripts_str != ""
            else []
        )

    @property
    def INIT_FILE_NAME(self) -> str:
        return os.getenv("ZRB_INIT_FILE_NAME", "zrb_init.py")

    @property
    def LOGGING_LEVEL(self) -> int:
        return self._get_log_level(os.getenv("ZRB_LOGGING_LEVEL", "WARNING"))

    def _get_log_level(self, level: str) -> int:
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

    @property
    def LOAD_BUILTIN(self) -> bool:
        return to_boolean(os.getenv("ZRB_LOAD_BUILTIN", "1"))

    @property
    def WARN_UNRECOMMENDED_COMMAND(self) -> bool:
        return to_boolean(os.getenv("ZRB_WARN_UNRECOMMENDED_COMMAND", "1"))

    @property
    def SESSION_LOG_DIR(self) -> str:
        return os.getenv(
            "ZRB_SESSION_LOG_DIR", os.path.expanduser(os.path.join("~", ".zrb-session"))
        )

    @property
    def TODO_DIR(self) -> str:
        return os.getenv("ZRB_TODO_DIR", os.path.expanduser(os.path.join("~", "todo")))

    @property
    def TODO_VISUAL_FILTER(self) -> str:
        return os.getenv("ZRB_TODO_FILTER", "")

    @property
    def TODO_RETENTION(self) -> str:
        return os.getenv("ZRB_TODO_RETENTION", "2w")

    @property
    def VERSION(self) -> str:
        return metadata.version("zrb")

    @property
    def WEB_HTTP_PORT(self) -> int:
        return int(os.getenv("ZRB_WEB_HTTP_PORT", "21213"))

    @property
    def WEB_GUEST_USERNAME(self) -> str:
        return os.getenv("ZRB_WEB_GUEST_USERNAME", "user")

    @property
    def WEB_SUPER_ADMIN_USERNAME(self) -> str:
        return os.getenv("ZRB_WEB_SUPERADMIN_USERNAME", "admin")

    @property
    def WEB_SUPER_ADMIN_PASSWORD(self) -> str:
        return os.getenv("ZRB_WEB_SUPERADMIN_PASSWORD", "admin")

    @property
    def WEB_ACCESS_TOKEN_COOKIE_NAME(self) -> str:
        return os.getenv("ZRB_WEB_ACCESS_TOKEN_COOKIE_NAME", "access_token")

    @property
    def WEB_REFRESH_TOKEN_COOKIE_NAME(self) -> str:
        return os.getenv("ZRB_WEB_REFRESH_TOKEN_COOKIE_NAME", "refresh_token")

    @property
    def WEB_SECRET_KEY(self) -> str:
        return os.getenv("ZRB_WEB_SECRET", "zrb")

    @property
    def WEB_ENABLE_AUTH(self) -> bool:
        return to_boolean(os.getenv("ZRB_WEB_ENABLE_AUTH", "0"))

    @property
    def WEB_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES(self) -> int:
        return int(os.getenv("ZRB_WEB_ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

    @property
    def WEB_AUTH_REFRESH_TOKEN_EXPIRE_MINUTES(self) -> int:
        return int(os.getenv("ZRB_WEB_REFRESH_TOKEN_EXPIRE_MINUTES", "60"))

    @property
    def WEB_TITLE(self) -> str:
        return os.getenv("ZRB_WEB_TITLE", "Zrb")

    @property
    def WEB_JARGON(self) -> str:
        return os.getenv("ZRB_WEB_JARGON", "Your Automation PowerHouse")

    @property
    def WEB_HOMEPAGE_INTRO(self) -> str:
        return os.getenv("ZRB_WEB_HOMEPAGE_INTRO", "Welcome to Zrb Web Interface")

    @property
    def LLM_HISTORY_DIR(self) -> str:
        return os.getenv(
            "ZRB_LLM_HISTORY_DIR",
            os.path.expanduser(os.path.join("~", ".zrb-llm-history")),
        )

    @property
    def LLM_ALLOW_ACCESS_LOCAL_FILE(self) -> bool:
        return to_boolean(os.getenv("ZRB_LLM_ACCESS_LOCAL_FILE", "1"))

    @property
    def LLM_ALLOW_ACCESS_SHELL(self) -> bool:
        return to_boolean(os.getenv("ZRB_LLM_ACCESS_SHELL", "1"))

    @property
    def LLM_ALLOW_ACCESS_INTERNET(self) -> bool:
        return to_boolean(os.getenv("ZRB_LLM_ACCESS_INTERNET", "1"))

    @property
    def RAG_EMBEDDING_API_KEY(self) -> str:
        return os.getenv("ZRB_RAG_EMBEDDING_API_KEY", None)

    @property
    def RAG_EMBEDDING_BASE_URL(self) -> str:
        return os.getenv("ZRB_RAG_EMBEDDING_BASE_URL", None)

    @property
    def RAG_EMBEDDING_MODEL(self) -> str:
        return os.getenv("ZRB_RAG_EMBEDDING_MODEL", "text-embedding-ada-002")

    @property
    def RAG_CHUNK_SIZE(self) -> int:
        return int(os.getenv("ZRB_RAG_CHUNK_SIZE", "1024"))

    @property
    def RAG_OVERLAP(self) -> int:
        return int(os.getenv("ZRB_RAG_OVERLAP", "128"))

    @property
    def RAG_MAX_RESULT_COUNT(self) -> int:
        return int(os.getenv("ZRB_RAG_MAX_RESULT_COUNT", "5"))

    @property
    def SERP_API_KEY(self) -> str:
        return os.getenv("SERP_API_KEY", "")

    @property
    def BANNER(self) -> str:
        return dedent(
            f"""
                            bb
               zzzzz rr rr  bb
                 zz  rrr  r bbbbbb
                zz   rr     bb   bb
               zzzzz rr     bbbbbb   {self.VERSION} Janggala
               _ _ . .  . _ .  _ . . .
            Your Automation Powerhouse
            ☕ Donate at: https://stalchmst.com/donation
            🐙 Submit issues/PR at: https://github.com/state-alchemists/zrb
            🐤 Follow us at: https://twitter.com/zarubastalchmst
            """
        ).strip()


CFG = Config()
