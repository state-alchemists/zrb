import importlib.metadata as metadata
import logging
import os
import platform

from zrb.util.string.conversion import to_boolean
from zrb.util.string.format import fstring_format

_DEFAULT_BANNER = """
                bb
   zzzzz rr rr  bb
     zz  rrr  r bbbbbb
    zz   rr     bb   bb
   zzzzz rr     bbbbbb   {VERSION} Janggala
   _ _ . .  . _ .  _ . . .
Your Automation Powerhouse
☕ Donate at: https://stalchmst.com
🐙 Submit issues/PR at: https://github.com/state-alchemists/zrb
🐤 Follow us at: https://twitter.com/zarubastalchmst
"""


class Config:
    def __init__(self):
        self.__internal_default_prompt: dict[str, str] = {}

    def _get_internal_default_prompt(self, name: str) -> str:
        if name not in self.__internal_default_prompt:
            file_path = os.path.join(
                os.path.dirname(__file__), "default_prompt", f"{name}.md"
            )
            with open(file_path, "r") as f:
                self.__internal_default_prompt[name] = f.read().strip()
        return self.__internal_default_prompt[name]

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
        if init_modules_str != "":
            return [
                module.strip()
                for module in init_modules_str.split(":")
                if module.strip() != ""
            ]
        return []

    @property
    def ROOT_GROUP_NAME(self) -> str:
        return os.getenv("ZRB_ROOT_GROUP_NAME", "zrb")

    @property
    def ROOT_GROUP_DESCRIPTION(self) -> str:
        return os.getenv("ZRB_ROOT_GROUP_DESCRIPTION", "Your Automation Powerhouse")

    @property
    def INIT_SCRIPTS(self) -> list[str]:
        init_scripts_str = os.getenv("ZRB_INIT_SCRIPTS", "")
        if init_scripts_str != "":
            return [
                script.strip()
                for script in init_scripts_str.split(":")
                if script.strip() != ""
            ]
        return []

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
        custom_version = os.getenv("_ZRB_CUSTOM_VERSION", "")
        if custom_version != "":
            return custom_version
        return metadata.version("zrb")

    @property
    def WEB_CSS_PATH(self) -> list[str]:
        web_css_path_str = os.getenv("ZRB_WEB_CSS_PATH", "")
        if web_css_path_str != "":
            return [
                path.strip()
                for path in web_css_path_str.split(":")
                if path.strip() != ""
            ]
        return []

    @property
    def WEB_JS_PATH(self) -> list[str]:
        web_js_path_str = os.getenv("ZRB_WEB_JS_PATH", "")
        if web_js_path_str != "":
            return [
                path.strip()
                for path in web_js_path_str.split(":")
                if path.strip() != ""
            ]
        return []

    @property
    def WEB_FAVICON_PATH(self) -> str:
        return os.getenv("ZRB_WEB_FAVICON_PATH", "/static/favicon-32x32.png")

    @property
    def WEB_COLOR(self) -> str:
        return os.getenv("ZRB_WEB_COLOR", "")

    @property
    def WEB_HTTP_PORT(self) -> int:
        return int(os.getenv("ZRB_WEB_HTTP_PORT", "21213"))

    @property
    def WEB_GUEST_USERNAME(self) -> str:
        return os.getenv("ZRB_WEB_GUEST_USERNAME", "user")

    @property
    def WEB_SUPER_ADMIN_USERNAME(self) -> str:
        return os.getenv("ZRB_WEB_SUPER_ADMIN_USERNAME", "admin")

    @property
    def WEB_SUPER_ADMIN_PASSWORD(self) -> str:
        return os.getenv("ZRB_WEB_SUPER_ADMIN_PASSWORD", "admin")

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
    def LLM_MODEL(self) -> str | None:
        return os.getenv("ZRB_LLM_MODEL", None)

    @property
    def LLM_BASE_URL(self) -> str | None:
        return os.getenv("ZRB_LLM_BASE_URL", None)

    @property
    def LLM_API_KEY(self) -> str | None:
        return os.getenv("ZRB_LLM_API_KEY", None)

    @property
    def LLM_SYSTEM_PROMPT(self) -> str | None:
        return os.getenv("ZRB_LLM_SYSTEM_PROMPT", None)

    @property
    def LLM_INTERACTIVE_SYSTEM_PROMPT(self) -> str | None:
        return os.getenv("ZRB_LLM_INTERACTIVE_SYSTEM_PROMPT", None)

    @property
    def LLM_PERSONA(self) -> str | None:
        return os.getenv("ZRB_LLM_PERSONA", None)

    @property
    def LLM_MODES(self) -> list[str]:
        return [
            mode.strip()
            for mode in os.getenv("ZRB_LLM_MODES", "coding").split(",")
            if mode.strip() != ""
        ]

    @property
    def LLM_SPECIAL_INSTRUCTION_PROMPT(self) -> str | None:
        return os.getenv("ZRB_LLM_SPECIAL_INSTRUCTION_PROMPT", None)

    @property
    def LLM_SUMMARIZATION_PROMPT(self) -> str | None:
        return os.getenv("ZRB_LLM_SUMMARIZATION_PROMPT", None)

    @property
    def LLM_MAX_REQUESTS_PER_MINUTE(self) -> int:
        """
        Maximum number of LLM requests allowed per minute.
        Default is conservative to accommodate free-tier LLM providers.
        """
        return int(os.getenv("LLM_MAX_REQUESTS_PER_MINUTE", "15"))

    @property
    def LLM_MAX_TOKENS_PER_MINUTE(self) -> int:
        """
        Maximum number of LLM tokens allowed per minute.
        Default is conservative to accommodate free-tier LLM providers.
        """
        return int(os.getenv("ZRB_LLM_MAX_TOKENS_PER_MINUTE", "100000"))

    @property
    def LLM_MAX_TOKENS_PER_REQUEST(self) -> int:
        """Maximum number of tokens allowed per individual LLM request."""
        return int(os.getenv("ZRB_LLM_MAX_TOKENS_PER_REQUEST", "50000"))

    @property
    def LLM_THROTTLE_SLEEP(self) -> float:
        """Number of seconds to sleep when throttling is required."""
        return float(os.getenv("ZRB_LLM_THROTTLE_SLEEP", "1.0"))

    @property
    def LLM_YOLO_MODE(self) -> bool:
        return to_boolean(os.getenv("ZRB_LLM_YOLO_MODE", "false"))

    @property
    def LLM_SUMMARIZE_HISTORY(self) -> bool:
        return to_boolean(os.getenv("ZRB_LLM_SUMMARIZE_HISTORY", "true"))

    @property
    def LLM_HISTORY_SUMMARIZATION_TOKEN_THRESHOLD(self) -> int:
        return int(os.getenv("ZRB_LLM_HISTORY_SUMMARIZATION_TOKEN_THRESHOLD", "20000"))

    @property
    def LLM_REPO_ANALYSIS_EXTRACTION_TOKEN_THRESHOLD(self) -> int:
        return int(os.getenv("ZRB_LLM_REPO_ANALYSIS_EXTRACTION_TOKEN_LIMIT", "35000"))

    @property
    def LLM_REPO_ANALYSIS_SUMMARIZATION_TOKEN_THRESHOLD(self) -> int:
        return int(
            os.getenv("ZRB_LLM_REPO_ANALYSIS_SUMMARIZATION_TOKEN_LIMIT", "35000")
        )

    @property
    def LLM_FILE_ANALYSIS_TOKEN_LIMIT(self) -> int:
        return int(os.getenv("ZRB_LLM_FILE_ANALYSIS_TOKEN_LIMIT", "35000"))

    @property
    def LLM_FILE_EXTRACTOR_SYSTEM_PROMPT(self) -> str:
        return os.getenv(
            "ZRB_LLM_FILE_EXTRACTOR_SYSTEM_PROMPT",
            self._get_internal_default_prompt("file_extractor_system_prompt"),
        )

    @property
    def LLM_REPO_EXTRACTOR_SYSTEM_PROMPT(self) -> str:
        return os.getenv(
            "ZRB_LLM_REPO_EXTRACTOR_SYSTEM_PROMPT",
            self._get_internal_default_prompt("repo_extractor_system_prompt"),
        )

    @property
    def LLM_REPO_SUMMARIZER_SYSTEM_PROMPT(self) -> str:
        return os.getenv(
            "ZRB_LLM_REPO_SUMMARIZER_SYSTEM_PROMPT",
            self._get_internal_default_prompt("repo_summarizer_system_prompt"),
        )

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
    def LLM_ALLOW_OPEN_WEB_PAGE(self) -> bool:
        return to_boolean(os.getenv("ZRB_LLM_ALLOW_OPEN_WEB_PAGE", "1"))

    @property
    def LLM_ALLOW_SEARCH_INTERNET(self) -> bool:
        return to_boolean(os.getenv("ZRB_LLM_ALLOW_SEARCH_INTERNET", "1"))

    @property
    def LLM_ALLOW_SEARCH_ARXIV(self) -> bool:
        return to_boolean(os.getenv("ZRB_LLM_ALLOW_SEARCH_ARXIV", "1"))

    @property
    def LLM_ALLOW_SEARCH_WIKIPEDIA(self) -> bool:
        return to_boolean(os.getenv("ZRB_LLM_ALLOW_SEARCH_WIKIPEDIA", "1"))

    @property
    def LLM_ALLOW_GET_CURRENT_LOCATION(self) -> bool:
        return to_boolean(os.getenv("ZRB_LLM_ALLOW_GET_CURRENT_LOCATION", "1"))

    @property
    def LLM_ALLOW_GET_CURRENT_WEATHER(self) -> bool:
        return to_boolean(os.getenv("ZRB_LLM_ALLOW_GET_CURRENT_WEATHER", "1"))

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
    def SERPAPI_KEY(self) -> str:
        return os.getenv("SERPAPI_KEY", "")

    @property
    def BANNER(self) -> str:
        return fstring_format(
            os.getenv("ZRB_BANNER", _DEFAULT_BANNER),
            {"VERSION": self.VERSION},
        )

    @property
    def LLM_CONTEXT_FILE(self) -> str:
        return os.getenv("LLM_CONTEXT_FILE", "ZRB.md")


CFG = Config()
