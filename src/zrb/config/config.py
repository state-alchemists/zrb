import importlib.metadata as metadata
import logging
import os

from zrb.config.helper import (
    get_current_shell,
    get_default_diff_edit_command,
    get_env,
    get_log_level,
    get_max_token_threshold,
    limit_token_threshold,
)
from zrb.util.string.conversion import to_boolean
from zrb.util.string.format import fstring_format

_DEFAULT_BANNER = """
                bb
   zzzzz rr rr  bb
     zz  rrr  r bbbbbb
    zz   rr     bb   bb
   zzzzz rr     bbbbbb   {VERSION} Pollux
   _ _ . .  . _ .  _ . . .
Your Automation Powerhouse
☕ Donate at: https://stalchmst.com
🐙 Submit issues/PR at: https://github.com/state-alchemists/zrb
🐤 Follow us at: https://twitter.com/zarubastalchmst
"""


class Config:
    def __init__(self):
        pass

    @property
    def ENV_PREFIX(self) -> str:
        return os.getenv("_ZRB_ENV_PREFIX", "ZRB")

    @ENV_PREFIX.setter
    def ENV_PREFIX(self, value: str):
        os.environ["_ZRB_ENV_PREFIX"] = value

    @property
    def LOGGER(self) -> logging.Logger:
        return logging.getLogger()

    @property
    def DEFAULT_SHELL(self) -> str:
        return get_env("SHELL", get_current_shell(), self.ENV_PREFIX)

    @DEFAULT_SHELL.setter
    def DEFAULT_SHELL(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_SHELL"] = value

    @property
    def DEFAULT_EDITOR(self) -> str:
        return get_env("EDITOR", "nano", self.ENV_PREFIX)

    @DEFAULT_EDITOR.setter
    def DEFAULT_EDITOR(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_EDITOR"] = value

    @property
    def DEFAULT_DIFF_EDIT_COMMAND_TPL(self) -> str:
        return get_env(
            "DIFF_EDIT_COMMAND",
            get_default_diff_edit_command(self.DEFAULT_EDITOR),
            self.ENV_PREFIX,
        )

    @DEFAULT_DIFF_EDIT_COMMAND_TPL.setter
    def DEFAULT_DIFF_EDIT_COMMAND_TPL(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_DIFF_EDIT_COMMAND"] = value

    @property
    def INIT_MODULES(self) -> list[str]:
        init_modules_str = get_env("INIT_MODULES", "", self.ENV_PREFIX)
        if init_modules_str != "":
            return [
                module.strip()
                for module in init_modules_str.split(":")
                if module.strip() != ""
            ]
        return []

    @INIT_MODULES.setter
    def INIT_MODULES(self, value: list[str]):
        os.environ[f"{self.ENV_PREFIX}_INIT_MODULES"] = ":".join(value)

    @property
    def ROOT_GROUP_NAME(self) -> str:
        return get_env("ROOT_GROUP_NAME", "zrb", self.ENV_PREFIX)

    @ROOT_GROUP_NAME.setter
    def ROOT_GROUP_NAME(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_ROOT_GROUP_NAME"] = value

    @property
    def ROOT_GROUP_DESCRIPTION(self) -> str:
        return get_env(
            "ROOT_GROUP_DESCRIPTION", "Your Automation Powerhouse", self.ENV_PREFIX
        )

    @ROOT_GROUP_DESCRIPTION.setter
    def ROOT_GROUP_DESCRIPTION(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_ROOT_GROUP_DESCRIPTION"] = value

    @property
    def INIT_SCRIPTS(self) -> list[str]:
        init_scripts_str = get_env("INIT_SCRIPTS", "", self.ENV_PREFIX)
        if init_scripts_str != "":
            return [
                script.strip()
                for script in init_scripts_str.split(":")
                if script.strip() != ""
            ]
        return []

    @INIT_SCRIPTS.setter
    def INIT_SCRIPTS(self, value: list[str]):
        os.environ[f"{self.ENV_PREFIX}_INIT_SCRIPTS"] = ":".join(value)

    @property
    def INIT_FILE_NAME(self) -> str:
        return get_env("INIT_FILE_NAME", "zrb_init.py", self.ENV_PREFIX)

    @INIT_FILE_NAME.setter
    def INIT_FILE_NAME(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_INIT_FILE_NAME"] = value

    @property
    def LOGGING_LEVEL(self) -> int:
        return get_log_level(get_env("LOGGING_LEVEL", "WARNING", self.ENV_PREFIX))

    @LOGGING_LEVEL.setter
    def LOGGING_LEVEL(self, value: int | str):
        if isinstance(value, int):
            value = logging.getLevelName(value)
        os.environ[f"{self.ENV_PREFIX}_LOGGING_LEVEL"] = str(value)

    @property
    def LOAD_BUILTIN(self) -> bool:
        return to_boolean(get_env("LOAD_BUILTIN", "1", self.ENV_PREFIX))

    @LOAD_BUILTIN.setter
    def LOAD_BUILTIN(self, value: bool):
        os.environ[f"{self.ENV_PREFIX}_LOAD_BUILTIN"] = "1" if value else "0"

    @property
    def WARN_UNRECOMMENDED_COMMAND(self) -> bool:
        return to_boolean(get_env("WARN_UNRECOMMENDED_COMMAND", "1", self.ENV_PREFIX))

    @WARN_UNRECOMMENDED_COMMAND.setter
    def WARN_UNRECOMMENDED_COMMAND(self, value: bool):
        os.environ[f"{self.ENV_PREFIX}_WARN_UNRECOMMENDED_COMMAND"] = (
            "1" if value else "0"
        )

    @property
    def SESSION_LOG_DIR(self) -> str:
        return os.getenv(
            "ZRB_SESSION_LOG_DIR",
            os.path.expanduser(os.path.join("~", f".{self.ROOT_GROUP_NAME}-session")),
        )

    @SESSION_LOG_DIR.setter
    def SESSION_LOG_DIR(self, value: str):
        os.environ["ZRB_SESSION_LOG_DIR"] = value

    @property
    def TODO_DIR(self) -> str:
        return get_env(
            "TODO_DIR",
            os.path.expanduser(os.path.join("~", "todo")),
            self.ENV_PREFIX,
        )

    @TODO_DIR.setter
    def TODO_DIR(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_TODO_DIR"] = value

    @property
    def TODO_VISUAL_FILTER(self) -> str:
        return get_env("TODO_FILTER", "", self.ENV_PREFIX)

    @TODO_VISUAL_FILTER.setter
    def TODO_VISUAL_FILTER(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_TODO_FILTER"] = value

    @property
    def TODO_RETENTION(self) -> str:
        return get_env("TODO_RETENTION", "2w", self.ENV_PREFIX)

    @TODO_RETENTION.setter
    def TODO_RETENTION(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_TODO_RETENTION"] = value

    @property
    def VERSION(self) -> str:
        custom_version = os.getenv("_ZRB_CUSTOM_VERSION", "")
        if custom_version != "":
            return custom_version
        return metadata.version("zrb")

    @VERSION.setter
    def VERSION(self, value: str):
        os.environ["_ZRB_CUSTOM_VERSION"] = value

    @property
    def WEB_CSS_PATH(self) -> list[str]:
        web_css_path_str = get_env("WEB_CSS_PATH", "", self.ENV_PREFIX)
        if web_css_path_str != "":
            return [
                path.strip()
                for path in web_css_path_str.split(":")
                if path.strip() != ""
            ]
        return []

    @WEB_CSS_PATH.setter
    def WEB_CSS_PATH(self, value: list[str]):
        os.environ[f"{self.ENV_PREFIX}_WEB_CSS_PATH"] = ":".join(value)

    @property
    def WEB_JS_PATH(self) -> list[str]:
        web_js_path_str = get_env("WEB_JS_PATH", "", self.ENV_PREFIX)
        if web_js_path_str != "":
            return [
                path.strip()
                for path in web_js_path_str.split(":")
                if path.strip() != ""
            ]
        return []

    @WEB_JS_PATH.setter
    def WEB_JS_PATH(self, value: list[str]):
        os.environ[f"{self.ENV_PREFIX}_WEB_JS_PATH"] = ":".join(value)

    @property
    def WEB_FAVICON_PATH(self) -> str:
        return get_env("WEB_FAVICON_PATH", "/static/favicon-32x32.png", self.ENV_PREFIX)

    @WEB_FAVICON_PATH.setter
    def WEB_FAVICON_PATH(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_WEB_FAVICON_PATH"] = value

    @property
    def WEB_COLOR(self) -> str:
        return get_env("WEB_COLOR", "", self.ENV_PREFIX)

    @WEB_COLOR.setter
    def WEB_COLOR(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_WEB_COLOR"] = value

    @property
    def WEB_HTTP_PORT(self) -> int:
        return int(get_env("WEB_HTTP_PORT", "21213", self.ENV_PREFIX))

    @WEB_HTTP_PORT.setter
    def WEB_HTTP_PORT(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_WEB_HTTP_PORT"] = str(value)

    @property
    def WEB_GUEST_USERNAME(self) -> str:
        return get_env("WEB_GUEST_USERNAME", "user", self.ENV_PREFIX)

    @WEB_GUEST_USERNAME.setter
    def WEB_GUEST_USERNAME(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_WEB_GUEST_USERNAME"] = value

    @property
    def WEB_SUPER_ADMIN_USERNAME(self) -> str:
        return get_env("WEB_SUPER_ADMIN_USERNAME", "admin", self.ENV_PREFIX)

    @WEB_SUPER_ADMIN_USERNAME.setter
    def WEB_SUPER_ADMIN_USERNAME(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_WEB_SUPER_ADMIN_USERNAME"] = value

    @property
    def WEB_SUPER_ADMIN_PASSWORD(self) -> str:
        return get_env("WEB_SUPER_ADMIN_PASSWORD", "admin", self.ENV_PREFIX)

    @WEB_SUPER_ADMIN_PASSWORD.setter
    def WEB_SUPER_ADMIN_PASSWORD(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_WEB_SUPER_ADMIN_PASSWORD"] = value

    @property
    def WEB_ACCESS_TOKEN_COOKIE_NAME(self) -> str:
        return get_env("WEB_ACCESS_TOKEN_COOKIE_NAME", "access_token", self.ENV_PREFIX)

    @WEB_ACCESS_TOKEN_COOKIE_NAME.setter
    def WEB_ACCESS_TOKEN_COOKIE_NAME(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_WEB_ACCESS_TOKEN_COOKIE_NAME"] = value

    @property
    def WEB_REFRESH_TOKEN_COOKIE_NAME(self) -> str:
        return get_env(
            "WEB_REFRESH_TOKEN_COOKIE_NAME", "refresh_token", self.ENV_PREFIX
        )

    @WEB_REFRESH_TOKEN_COOKIE_NAME.setter
    def WEB_REFRESH_TOKEN_COOKIE_NAME(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_WEB_REFRESH_TOKEN_COOKIE_NAME"] = value

    @property
    def WEB_SECRET_KEY(self) -> str:
        return get_env("WEB_SECRET", "zrb", self.ENV_PREFIX)

    @WEB_SECRET_KEY.setter
    def WEB_SECRET_KEY(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_WEB_SECRET"] = value

    @property
    def WEB_ENABLE_AUTH(self) -> bool:
        return to_boolean(get_env("WEB_ENABLE_AUTH", "0", self.ENV_PREFIX))

    @WEB_ENABLE_AUTH.setter
    def WEB_ENABLE_AUTH(self, value: bool):
        os.environ[f"{self.ENV_PREFIX}_WEB_ENABLE_AUTH"] = "1" if value else "0"

    @property
    def WEB_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES(self) -> int:
        return int(get_env("WEB_ACCESS_TOKEN_EXPIRE_MINUTES", "30", self.ENV_PREFIX))

    @WEB_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES.setter
    def WEB_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_WEB_ACCESS_TOKEN_EXPIRE_MINUTES"] = str(value)

    @property
    def WEB_AUTH_REFRESH_TOKEN_EXPIRE_MINUTES(self) -> int:
        return int(get_env("WEB_REFRESH_TOKEN_EXPIRE_MINUTES", "60", self.ENV_PREFIX))

    @WEB_AUTH_REFRESH_TOKEN_EXPIRE_MINUTES.setter
    def WEB_AUTH_REFRESH_TOKEN_EXPIRE_MINUTES(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_WEB_REFRESH_TOKEN_EXPIRE_MINUTES"] = str(value)

    @property
    def WEB_TITLE(self) -> str:
        return get_env("WEB_TITLE", "Zrb", self.ENV_PREFIX)

    @WEB_TITLE.setter
    def WEB_TITLE(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_WEB_TITLE"] = value

    @property
    def WEB_JARGON(self) -> str:
        return get_env("WEB_JARGON", "Your Automation PowerHouse", self.ENV_PREFIX)

    @WEB_JARGON.setter
    def WEB_JARGON(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_WEB_JARGON"] = value

    @property
    def WEB_HOMEPAGE_INTRO(self) -> str:
        return get_env(
            "WEB_HOMEPAGE_INTRO", "Welcome to Zrb Web Interface", self.ENV_PREFIX
        )

    @WEB_HOMEPAGE_INTRO.setter
    def WEB_HOMEPAGE_INTRO(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_WEB_HOMEPAGE_INTRO"] = value

    @property
    def LLM_HISTORY_DIR(self) -> str:
        return os.getenv(
            "ZRB_LLM_HISTORY_DIR",
            os.path.expanduser(
                os.path.join("~", f".{self.ROOT_GROUP_NAME}-llm-history")
            ),
        )

    @LLM_HISTORY_DIR.setter
    def LLM_HISTORY_DIR(self, value: str):
        os.environ["ZRB_LLM_HISTORY_DIR"] = value

    @property
    def LLM_MODEL(self) -> str | None:
        value = get_env("LLM_MODEL", "", self.ENV_PREFIX)
        return None if value == "" else value

    @LLM_MODEL.setter
    def LLM_MODEL(self, value: str | None):
        if value is None:
            if f"{self.ENV_PREFIX}_LLM_MODEL" in os.environ:
                del os.environ[f"{self.ENV_PREFIX}_LLM_MODEL"]
        else:
            os.environ[f"{self.ENV_PREFIX}_LLM_MODEL"] = value

    @property
    def LLM_BASE_URL(self) -> str | None:
        value = get_env("LLM_BASE_URL", "", self.ENV_PREFIX)
        return None if value == "" else value

    @LLM_BASE_URL.setter
    def LLM_BASE_URL(self, value: str | None):
        if value is None:
            if f"{self.ENV_PREFIX}_LLM_BASE_URL" in os.environ:
                del os.environ[f"{self.ENV_PREFIX}_LLM_BASE_URL"]
        else:
            os.environ[f"{self.ENV_PREFIX}_LLM_BASE_URL"] = value

    @property
    def LLM_API_KEY(self) -> str | None:
        value = get_env("LLM_API_KEY", "", self.ENV_PREFIX)
        return None if value == "" else value

    @LLM_API_KEY.setter
    def LLM_API_KEY(self, value: str | None):
        if value is None:
            if f"{self.ENV_PREFIX}_LLM_API_KEY" in os.environ:
                del os.environ[f"{self.ENV_PREFIX}_LLM_API_KEY"]
        else:
            os.environ[f"{self.ENV_PREFIX}_LLM_API_KEY"] = value

    @property
    def LLM_MAX_REQUESTS_PER_MINUTE(self) -> int:
        """
        Maximum number of LLM requests allowed per minute.
        Default is conservative to accommodate free-tier LLM providers.
        """
        return int(
            get_env(
                ["LLM_MAX_REQUEST_PER_MINUTE", "LLM_MAX_REQUESTS_PER_MINUTE"],
                "60",
                self.ENV_PREFIX,
            )
        )

    @LLM_MAX_REQUESTS_PER_MINUTE.setter
    def LLM_MAX_REQUESTS_PER_MINUTE(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_LLM_MAX_REQUESTS_PER_MINUTE"] = str(value)

    @property
    def LLM_MAX_TOKENS_PER_MINUTE(self) -> int:
        """
        Maximum number of LLM tokens allowed per minute.
        Default is conservative to accommodate free-tier LLM providers.
        """
        return int(
            get_env(
                ["LLM_MAX_TOKEN_PER_MINUTE", "LLM_MAX_TOKENS_PER_MINUTE"],
                "120000",
                self.ENV_PREFIX,
            )
        )

    @LLM_MAX_TOKENS_PER_MINUTE.setter
    def LLM_MAX_TOKENS_PER_MINUTE(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_LLM_MAX_TOKENS_PER_MINUTE"] = str(value)

    @property
    def LLM_MAX_TOKENS_PER_REQUEST(self) -> int:
        """Maximum number of tokens allowed per individual LLM request."""
        return int(
            get_env(
                ["LLM_MAX_TOKEN_PER_REQUEST", "LLM_MAX_TOKENS_PER_REQUEST"],
                "120000",
                self.ENV_PREFIX,
            )
        )

    @LLM_MAX_TOKENS_PER_REQUEST.setter
    def LLM_MAX_TOKENS_PER_REQUEST(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_LLM_MAX_TOKENS_PER_REQUEST"] = str(value)

    @property
    def LLM_THROTTLE_SLEEP(self) -> float:
        """Number of seconds to sleep when throttling is required."""
        return float(get_env("LLM_THROTTLE_SLEEP", "1.0", self.ENV_PREFIX))

    @LLM_THROTTLE_SLEEP.setter
    def LLM_THROTTLE_SLEEP(self, value: float):
        os.environ[f"{self.ENV_PREFIX}_LLM_THROTTLE_SLEEP"] = str(value)

    @property
    def LLM_HISTORY_SUMMARIZATION_WINDOW(self) -> int:
        return int(get_env("LLM_HISTORY_SUMMARIZATION_WINDOW", "5", self.ENV_PREFIX))

    @LLM_HISTORY_SUMMARIZATION_WINDOW.setter
    def LLM_HISTORY_SUMMARIZATION_WINDOW(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_LLM_HISTORY_SUMMARIZATION_WINDOW"] = str(value)

    @property
    def LLM_HISTORY_SUMMARIZATION_TOKEN_THRESHOLD(self) -> int:
        threshold = int(
            get_env(
                "LLM_HISTORY_SUMMARIZATION_TOKEN_THRESHOLD",
                str(self._get_max_threshold(0.6)),
                self.ENV_PREFIX,
            )
        )
        return limit_token_threshold(
            threshold,
            0.6,
            self.LLM_MAX_TOKENS_PER_MINUTE,
            self.LLM_MAX_TOKENS_PER_REQUEST,
        )

    @LLM_HISTORY_SUMMARIZATION_TOKEN_THRESHOLD.setter
    def LLM_HISTORY_SUMMARIZATION_TOKEN_THRESHOLD(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_LLM_HISTORY_SUMMARIZATION_TOKEN_THRESHOLD"] = (
            str(value)
        )

    @property
    def LLM_REPO_ANALYSIS_EXTRACTION_TOKEN_THRESHOLD(self) -> int:
        threshold = int(
            get_env(
                "LLM_REPO_ANALYSIS_EXTRACTION_TOKEN_THRESHOLD",
                str(self._get_max_threshold(0.4)),
                self.ENV_PREFIX,
            )
        )
        return limit_token_threshold(
            threshold,
            0.4,
            self.LLM_MAX_TOKENS_PER_MINUTE,
            self.LLM_MAX_TOKENS_PER_REQUEST,
        )

    @LLM_REPO_ANALYSIS_EXTRACTION_TOKEN_THRESHOLD.setter
    def LLM_REPO_ANALYSIS_EXTRACTION_TOKEN_THRESHOLD(self, value: int):
        os.environ[
            f"{self.ENV_PREFIX}_LLM_REPO_ANALYSIS_EXTRACTION_TOKEN_THRESHOLD"
        ] = str(value)

    @property
    def LLM_REPO_ANALYSIS_SUMMARIZATION_TOKEN_THRESHOLD(self) -> int:
        threshold = int(
            get_env(
                "LLM_REPO_ANALYSIS_SUMMARIZATION_TOKEN_THRESHOLD",
                str(self._get_max_threshold(0.4)),
                self.ENV_PREFIX,
            )
        )
        return limit_token_threshold(
            threshold,
            0.4,
            self.LLM_MAX_TOKENS_PER_MINUTE,
            self.LLM_MAX_TOKENS_PER_REQUEST,
        )

    @LLM_REPO_ANALYSIS_SUMMARIZATION_TOKEN_THRESHOLD.setter
    def LLM_REPO_ANALYSIS_SUMMARIZATION_TOKEN_THRESHOLD(self, value: int):
        os.environ[
            f"{self.ENV_PREFIX}_LLM_REPO_ANALYSIS_SUMMARIZATION_TOKEN_THRESHOLD"
        ] = str(value)

    @property
    def LLM_FILE_ANALYSIS_TOKEN_THRESHOLD(self) -> int:
        threshold = int(
            get_env(
                "LLM_FILE_ANALYSIS_TOKEN_THRESHOLD",
                str(self._get_max_threshold(0.4)),
                self.ENV_PREFIX,
            )
        )
        return limit_token_threshold(
            threshold,
            0.4,
            self.LLM_MAX_TOKENS_PER_MINUTE,
            self.LLM_MAX_TOKENS_PER_REQUEST,
        )

    @LLM_FILE_ANALYSIS_TOKEN_THRESHOLD.setter
    def LLM_FILE_ANALYSIS_TOKEN_THRESHOLD(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_LLM_FILE_ANALYSIS_TOKEN_THRESHOLD"] = str(value)

    def _get_max_threshold(self, factor: float) -> int:
        return get_max_token_threshold(
            factor, self.LLM_MAX_TOKENS_PER_MINUTE, self.LLM_MAX_TOKENS_PER_REQUEST
        )

    @property
    def RAG_EMBEDDING_API_KEY(self) -> str | None:
        value = get_env("RAG_EMBEDDING_API_KEY", "", self.ENV_PREFIX)
        return None if value == "" else value

    @RAG_EMBEDDING_API_KEY.setter
    def RAG_EMBEDDING_API_KEY(self, value: str | None):
        if value is None:
            if f"{self.ENV_PREFIX}_RAG_EMBEDDING_API_KEY" in os.environ:
                del os.environ[f"{self.ENV_PREFIX}_RAG_EMBEDDING_API_KEY"]
        else:
            os.environ[f"{self.ENV_PREFIX}_RAG_EMBEDDING_API_KEY"] = value

    @property
    def RAG_EMBEDDING_BASE_URL(self) -> str | None:
        value = get_env("RAG_EMBEDDING_BASE_URL", "", self.ENV_PREFIX)
        return None if value == "" else value

    @RAG_EMBEDDING_BASE_URL.setter
    def RAG_EMBEDDING_BASE_URL(self, value: str | None):
        if value is None:
            if f"{self.ENV_PREFIX}_RAG_EMBEDDING_BASE_URL" in os.environ:
                del os.environ[f"{self.ENV_PREFIX}_RAG_EMBEDDING_BASE_URL"]
        else:
            os.environ[f"{self.ENV_PREFIX}_RAG_EMBEDDING_BASE_URL"] = value

    @property
    def RAG_EMBEDDING_MODEL(self) -> str:
        return get_env("RAG_EMBEDDING_MODEL", "text-embedding-ada-002", self.ENV_PREFIX)

    @RAG_EMBEDDING_MODEL.setter
    def RAG_EMBEDDING_MODEL(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_RAG_EMBEDDING_MODEL"] = value

    @property
    def RAG_CHUNK_SIZE(self) -> int:
        return int(get_env("RAG_CHUNK_SIZE", "1024", self.ENV_PREFIX))

    @RAG_CHUNK_SIZE.setter
    def RAG_CHUNK_SIZE(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_RAG_CHUNK_SIZE"] = str(value)

    @property
    def RAG_OVERLAP(self) -> int:
        return int(get_env("RAG_OVERLAP", "128", self.ENV_PREFIX))

    @RAG_OVERLAP.setter
    def RAG_OVERLAP(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_RAG_OVERLAP"] = str(value)

    @property
    def RAG_MAX_RESULT_COUNT(self) -> int:
        return int(get_env("RAG_MAX_RESULT_COUNT", "5", self.ENV_PREFIX))

    @RAG_MAX_RESULT_COUNT.setter
    def RAG_MAX_RESULT_COUNT(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_RAG_MAX_RESULT_COUNT"] = str(value)

    @property
    def SEARCH_INTERNET_METHOD(self) -> str:
        """Either serpapi or searxng"""
        return get_env("SEARCH_INTERNET_METHOD", "serpapi", self.ENV_PREFIX)

    @SEARCH_INTERNET_METHOD.setter
    def SEARCH_INTERNET_METHOD(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_SEARCH_INTERNET_METHOD"] = value

    @property
    def BRAVE_API_KEY(self) -> str:
        return os.getenv("BRAVE_API_KEY", "")

    @BRAVE_API_KEY.setter
    def BRAVE_API_KEY(self, value: str):
        os.environ["BRAVE_API_KEY"] = value

    @property
    def BRAVE_API_SAFE(self) -> str:
        return get_env("BRAVE_API_SAFE", "off", self.ENV_PREFIX)

    @BRAVE_API_SAFE.setter
    def BRAVE_API_SAFE(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_BRAVE_API_SAFE"] = value

    @property
    def BRAVE_API_LANG(self) -> str:
        return get_env("BRAVE_API_LANG", "en", self.ENV_PREFIX)

    @BRAVE_API_LANG.setter
    def BRAVE_API_LANG(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_BRAVE_API_LANG"] = value

    @property
    def SERPAPI_KEY(self) -> str:
        return os.getenv("SERPAPI_KEY", "")

    @SERPAPI_KEY.setter
    def SERPAPI_KEY(self, value: str):
        os.environ["SERPAPI_KEY"] = value

    @property
    def SERPAPI_SAFE(self) -> str:
        return get_env("SERPAPI_SAFE", "off", self.ENV_PREFIX)

    @SERPAPI_SAFE.setter
    def SERPAPI_SAFE(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_SERPAPI_SAFE"] = value

    @property
    def SERPAPI_LANG(self) -> str:
        return get_env("SERPAPI_LANG", "en", self.ENV_PREFIX)

    @SERPAPI_LANG.setter
    def SERPAPI_LANG(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_SERPAPI_LANG"] = value

    @property
    def SEARXNG_PORT(self) -> int:
        return int(get_env("SEARXNG_PORT", "8080", self.ENV_PREFIX))

    @SEARXNG_PORT.setter
    def SEARXNG_PORT(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_SEARXNG_PORT"] = str(value)

    @property
    def SEARXNG_BASE_URL(self) -> str:
        return get_env(
            "SEARXNG_BASE_URL", f"http://localhost:{self.SEARXNG_PORT}", self.ENV_PREFIX
        )

    @SEARXNG_BASE_URL.setter
    def SEARXNG_BASE_URL(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_SEARXNG_BASE_URL"] = value

    @property
    def SEARXNG_SAFE(self) -> int:
        return int(get_env("SEARXNG_SAFE", "0", self.ENV_PREFIX))

    @SEARXNG_SAFE.setter
    def SEARXNG_SAFE(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_SEARXNG_SAFE"] = str(value)

    @property
    def SEARXNG_LANG(self) -> str:
        return get_env("SEARXNG_LANG", "en", self.ENV_PREFIX)

    @SEARXNG_LANG.setter
    def SEARXNG_LANG(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_SEARXNG_LANG"] = value

    @property
    def BANNER(self) -> str:
        return fstring_format(
            get_env("BANNER", _DEFAULT_BANNER, self.ENV_PREFIX),
            {"VERSION": self.VERSION},
        )

    @BANNER.setter
    def BANNER(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_BANNER"] = value

    @property
    def USE_TIKTOKEN(self) -> bool:
        return to_boolean(get_env("USE_TIKTOKEN", "true", self.ENV_PREFIX))

    @USE_TIKTOKEN.setter
    def USE_TIKTOKEN(self, value: bool):
        os.environ[f"{self.ENV_PREFIX}_USE_TIKTOKEN"] = "1" if value else "0"

    @property
    def TIKTOKEN_ENCODING_NAME(self) -> str:
        return get_env(
            ["TIKTOKEN_ENCODING", "TIKTOKEN_ENCODING_NAME"],
            "cl100k_base",
            self.ENV_PREFIX,
        )

    @TIKTOKEN_ENCODING_NAME.setter
    def TIKTOKEN_ENCODING_NAME(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_TIKTOKEN_ENCODING_NAME"] = value


CFG = Config()
