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
        self.DEFAULT_ENV_PREFIX: str = "ZRB"
        self.DEFAULT_SHELL: str = ""
        self.DEFAULT_EDITOR: str = "nano"
        self.DEFAULT_EDIT_COMMAND_TPL: str = ""
        self.DEFAULT_INIT_MODULES: str = ""
        self.DEFAULT_ROOT_GROUP_NAME: str = "zrb"
        self.DEFAULT_ROOT_GROUP_DESCRIPTION: str = "Your Automation Powerhouse"
        self.DEFAULT_INIT_SCRIPTS: str = ""
        self.DEFAULT_INIT_FILE_NAME: str = "zrb_init.py"
        self.DEFAULT_LOGGING_LEVEL: str = "WARNING"
        self.DEFAULT_LOAD_BUILTIN: str = "1"
        self.DEFAULT_WARN_UNRECOMMENDED_COMMAND: str = "on"
        self.DEFAULT_SESSION_LOG_DIR: str = ""
        self.DEFAULT_TODO_DIR: str = ""
        self.DEFAULT_TODO_VISUAL_FILTER: str = ""
        self.DEFAULT_TODO_RETENTION: str = "2w"
        self.DEFAULT_VERSION: str = ""
        self.DEFAULT_WEB_CSS_PATH: str = ""
        self.DEFAULT_WEB_JS_PATH: str = ""
        self.DEFAULT_WEB_FAVICON_PATH: str = "/static/favicon-32x32.png"
        self.DEFAULT_WEB_COLOR: str = ""
        self.DEFAULT_WEB_HTTP_PORT: str = "21213"
        self.DEFAULT_WEB_GUEST_USERNAME: str = "user"
        self.DEFAULT_WEB_SUPER_ADMIN_USERNAME: str = "admin"
        self.DEFAULT_WEB_SUPER_ADMIN_PASSWORD: str = "admin"
        self.DEFAULT_WEB_ACCESS_TOKEN_COOKIE_NAME: str = "access_token"
        self.DEFAULT_WEB_REFRESH_TOKEN_COOKIE_NAME: str = "refresh_token"
        self.DEFAULT_WEB_SECRET_KEY: str = "zrb"
        self.DEFAULT_WEB_ENABLE_AUTH: str = "0"
        self.DEFAULT_WEB_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES: str = "30"
        self.DEFAULT_WEB_AUTH_REFRESH_TOKEN_EXPIRE_MINUTES: str = "60"
        self.DEFAULT_WEB_TITLE: str = "Zrb"
        self.DEFAULT_WEB_JARGON: str = "Your Automation PowerHouse"
        self.DEFAULT_WEB_HOMEPAGE_INTRO: str = "Welcome to Zrb Web Interface"
        self.DEFAULT_LLM_ASSISTANT_NAME: str = ""
        self.DEFAULT_LLM_ASSISTANT_ASCII_ART: str = "default"
        self.DEFAULT_LLM_ASSISTANT_JARGON: str = ""
        self.DEFAULT_LLM_UI_STYLE_TITLE_BAR: str = "#ffffff"
        self.DEFAULT_LLM_UI_STYLE_INFO_BAR: str = "#ffffff"
        self.DEFAULT_LLM_UI_STYLE_FRAME: str = "#888888"
        self.DEFAULT_LLM_UI_STYLE_FRAME_LABEL: str = "#ffff00"
        self.DEFAULT_LLM_UI_STYLE_INPUT_FRAME: str = "#888888"
        self.DEFAULT_LLM_UI_STYLE_THINKING: str = "ansigreen italic"
        self.DEFAULT_LLM_UI_STYLE_FAINT: str = "#888888"
        self.DEFAULT_LLM_UI_STYLE_OUTPUT_FIELD: str = "#eeeeee"
        self.DEFAULT_LLM_UI_STYLE_INPUT_FIELD: str = "#eeeeee"
        self.DEFAULT_LLM_UI_STYLE_TEXT: str = "#eeeeee"
        self.DEFAULT_LLM_UI_STYLE_STATUS: str = "reverse"
        self.DEFAULT_LLM_UI_STYLE_BOTTOM_TOOLBAR: str = "bg:#333333 #aaaaaa"
        self.DEFAULT_LLM_UI_COMMAND_SUMMARIZE: str = "/compress, /compact"
        self.DEFAULT_LLM_UI_COMMAND_ATTACH: str = "/attach"
        self.DEFAULT_LLM_UI_COMMAND_EXIT: str = "/q, /bye, /quit, /exit"
        self.DEFAULT_LLM_UI_COMMAND_INFO: str = "/info, /help"
        self.DEFAULT_LLM_UI_COMMAND_SAVE: str = "/save"
        self.DEFAULT_LLM_UI_COMMAND_LOAD: str = "/load"
        self.DEFAULT_LLM_UI_COMMAND_YOLO_TOGGLE: str = "/yolo"
        self.DEFAULT_LLM_UI_COMMAND_REDIRECT_OUTPUT: str = ">, /redirect"
        self.DEFAULT_LLM_UI_COMMAND_EXEC: str = "!, /exec"
        self.DEFAULT_LLM_HISTORY_DIR: str = ""
        self.DEFAULT_LLM_NOTE_FILE: str = ""
        self.DEFAULT_LLM_MODEL: str = ""
        self.DEFAULT_LLM_BASE_URL: str = ""
        self.DEFAULT_LLM_API_KEY: str = ""
        self.DEFAULT_LLM_MAX_REQUEST_PER_MINUTE: str = "60"
        self.DEFAULT_LLM_MAX_TOKENS_PER_MINUTE: str = "120000"
        self.DEFAULT_LLM_MAX_TOKENS_PER_REQUEST: str = "120000"
        self.DEFAULT_LLM_THROTTLE_SLEEP: str = "1.0"
        self.DEFAULT_LLM_HISTORY_SUMMARIZATION_WINDOW: str = "5"
        self.DEFAULT_LLM_HISTORY_SUMMARIZATION_TOKEN_THRESHOLD: str = ""
        self.DEFAULT_LLM_REPO_ANALYSIS_EXTRACTION_TOKEN_THRESHOLD: str = ""
        self.DEFAULT_LLM_REPO_ANALYSIS_SUMMARIZATION_TOKEN_THRESHOLD: str = ""
        self.DEFAULT_LLM_FILE_ANALYSIS_TOKEN_THRESHOLD: str = ""
        self.DEFAULT_LLM_PROMPT_DIR: str = ""
        self.DEFAULT_LLM_SHOW_TOOL_CALL_DETAIL: str = "off"
        self.DEFAULT_LLM_SHOW_TOOL_CALL_RESULT: str = "off"
        self.DEFAULT_ASCII_ART_DIR: str = ""
        self.DEFAULT_RAG_EMBEDDING_API_KEY: str = ""
        self.DEFAULT_RAG_EMBEDDING_BASE_URL: str = ""
        self.DEFAULT_RAG_EMBEDDING_MODEL: str = "text-embedding-ada-002"
        self.DEFAULT_RAG_CHUNK_SIZE: str = "1024"
        self.DEFAULT_RAG_OVERLAP: str = "128"
        self.DEFAULT_RAG_MAX_RESULT_COUNT: str = "5"
        self.DEFAULT_SEARCH_INTERNET_METHOD: str = "serpapi"
        self.DEFAULT_BRAVE_API_KEY: str = ""
        self.DEFAULT_BRAVE_API_SAFE: str = "off"
        self.DEFAULT_BRAVE_API_LANG: str = "en"
        self.DEFAULT_SERPAPI_KEY: str = ""
        self.DEFAULT_SERPAPI_SAFE: str = "off"
        self.DEFAULT_SERPAPI_LANG: str = "en"
        self.DEFAULT_SEARXNG_PORT: str = "8080"
        self.DEFAULT_SEARXNG_BASE_URL: str = ""
        self.DEFAULT_SEARXNG_SAFE: str = "0"
        self.DEFAULT_SEARXNG_LANG: str = "en-US"
        self.DEFAULT_BANNER: str = _DEFAULT_BANNER
        self.DEFAULT_USE_TIKTOKEN: str = "off"
        self.DEFAULT_TIKTOKEN_ENCODING_NAME: str = "cl100k_base"
        self.DEFAULT_MCP_CONFIG_FILE: str = "mcp-config.json"

    @property
    def ENV_PREFIX(self) -> str:
        return os.getenv("_ZRB_ENV_PREFIX", self.DEFAULT_ENV_PREFIX)

    @ENV_PREFIX.setter
    def ENV_PREFIX(self, value: str):
        os.environ["_ZRB_ENV_PREFIX"] = value

    @property
    def LOGGER(self) -> logging.Logger:
        return logging.getLogger()

    @property
    def SHELL(self) -> str:
        return get_env(
            "SHELL",
            (self.DEFAULT_SHELL if self.DEFAULT_SHELL != "" else get_current_shell()),
            self.ENV_PREFIX,
        )

    @SHELL.setter
    def SHELL(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_SHELL"] = value

    @property
    def EDITOR(self) -> str:
        return get_env("EDITOR", self.DEFAULT_EDITOR, self.ENV_PREFIX)

    @EDITOR.setter
    def EDITOR(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_EDITOR"] = value

    @property
    def DIFF_EDIT_COMMAND_TPL(self) -> str:
        return get_env(
            "DIFF_EDIT_COMMAND",
            (
                self.DEFAULT_EDIT_COMMAND_TPL
                if self.DEFAULT_EDIT_COMMAND_TPL != ""
                else get_default_diff_edit_command(self.EDITOR)
            ),
            self.ENV_PREFIX,
        )

    @DIFF_EDIT_COMMAND_TPL.setter
    def DIFF_EDIT_COMMAND_TPL(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_DIFF_EDIT_COMMAND"] = value

    @property
    def INIT_MODULES(self) -> list[str]:
        init_modules_str = get_env(
            "INIT_MODULES", self.DEFAULT_INIT_MODULES, self.ENV_PREFIX
        )
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
        return get_env("ROOT_GROUP_NAME", self.DEFAULT_ROOT_GROUP_NAME, self.ENV_PREFIX)

    @ROOT_GROUP_NAME.setter
    def ROOT_GROUP_NAME(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_ROOT_GROUP_NAME"] = value

    @property
    def ROOT_GROUP_DESCRIPTION(self) -> str:
        return get_env(
            "ROOT_GROUP_DESCRIPTION",
            self.DEFAULT_ROOT_GROUP_DESCRIPTION,
            self.ENV_PREFIX,
        )

    @ROOT_GROUP_DESCRIPTION.setter
    def ROOT_GROUP_DESCRIPTION(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_ROOT_GROUP_DESCRIPTION"] = value

    @property
    def INIT_SCRIPTS(self) -> list[str]:
        init_scripts_str = get_env(
            "INIT_SCRIPTS", self.DEFAULT_INIT_SCRIPTS, self.ENV_PREFIX
        )
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
        return get_env("INIT_FILE_NAME", self.DEFAULT_INIT_FILE_NAME, self.ENV_PREFIX)

    @INIT_FILE_NAME.setter
    def INIT_FILE_NAME(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_INIT_FILE_NAME"] = value

    @property
    def LOGGING_LEVEL(self) -> int:
        return get_log_level(
            get_env("LOGGING_LEVEL", self.DEFAULT_LOGGING_LEVEL, self.ENV_PREFIX)
        )

    @LOGGING_LEVEL.setter
    def LOGGING_LEVEL(self, value: int | str):
        if isinstance(value, int):
            value = logging.getLevelName(value)
        os.environ[f"{self.ENV_PREFIX}_LOGGING_LEVEL"] = str(value)

    @property
    def LOAD_BUILTIN(self) -> bool:
        return to_boolean(
            get_env("LOAD_BUILTIN", self.DEFAULT_LOAD_BUILTIN, self.ENV_PREFIX)
        )

    @LOAD_BUILTIN.setter
    def LOAD_BUILTIN(self, value: bool):
        os.environ[f"{self.ENV_PREFIX}_LOAD_BUILTIN"] = "1" if value else "0"

    @property
    def WARN_UNRECOMMENDED_COMMAND(self) -> bool:
        return to_boolean(
            get_env(
                "WARN_UNRECOMMENDED_COMMAND",
                self.DEFAULT_WARN_UNRECOMMENDED_COMMAND,
                self.ENV_PREFIX,
            )
        )

    @WARN_UNRECOMMENDED_COMMAND.setter
    def WARN_UNRECOMMENDED_COMMAND(self, value: bool):
        os.environ[f"{self.ENV_PREFIX}_WARN_UNRECOMMENDED_COMMAND"] = (
            "1" if value else "0"
        )

    @property
    def SESSION_LOG_DIR(self) -> str:
        default = self.DEFAULT_SESSION_LOG_DIR
        if default == "":
            default = os.path.expanduser(
                os.path.join("~", f".{self.ROOT_GROUP_NAME}", "session")
            )
        return get_env(
            "SESSION_LOG_DIR",
            default,
            self.ENV_PREFIX,
        )

    @SESSION_LOG_DIR.setter
    def SESSION_LOG_DIR(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_SESSION_LOG_DIR"] = value

    @property
    def TODO_DIR(self) -> str:
        default = self.DEFAULT_TODO_DIR
        if default == "":
            default = os.path.expanduser(os.path.join("~", "todo"))
        return get_env(
            "TODO_DIR",
            default,
            self.ENV_PREFIX,
        )

    @TODO_DIR.setter
    def TODO_DIR(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_TODO_DIR"] = value

    @property
    def TODO_VISUAL_FILTER(self) -> str:
        return get_env("TODO_FILTER", self.DEFAULT_TODO_VISUAL_FILTER, self.ENV_PREFIX)

    @TODO_VISUAL_FILTER.setter
    def TODO_VISUAL_FILTER(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_TODO_FILTER"] = value

    @property
    def TODO_RETENTION(self) -> str:
        return get_env("TODO_RETENTION", self.DEFAULT_TODO_RETENTION, self.ENV_PREFIX)

    @TODO_RETENTION.setter
    def TODO_RETENTION(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_TODO_RETENTION"] = value

    @property
    def VERSION(self) -> str:
        custom_version = os.getenv("_ZRB_CUSTOM_VERSION", "")
        if custom_version != "":
            return custom_version
        return (
            self.DEFAULT_VERSION
            if self.DEFAULT_VERSION != ""
            else metadata.version("zrb")
        )

    @VERSION.setter
    def VERSION(self, value: str):
        os.environ["_ZRB_CUSTOM_VERSION"] = value

    @property
    def WEB_CSS_PATH(self) -> list[str]:
        web_css_path_str = get_env(
            "WEB_CSS_PATH", self.DEFAULT_WEB_CSS_PATH, self.ENV_PREFIX
        )
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
        web_js_path_str = get_env(
            "WEB_JS_PATH", self.DEFAULT_WEB_JS_PATH, self.ENV_PREFIX
        )
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
        return get_env(
            "WEB_FAVICON_PATH", self.DEFAULT_WEB_FAVICON_PATH, self.ENV_PREFIX
        )

    @WEB_FAVICON_PATH.setter
    def WEB_FAVICON_PATH(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_WEB_FAVICON_PATH"] = value

    @property
    def WEB_COLOR(self) -> str:
        return get_env("WEB_COLOR", self.DEFAULT_WEB_COLOR, self.ENV_PREFIX)

    @WEB_COLOR.setter
    def WEB_COLOR(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_WEB_COLOR"] = value

    @property
    def WEB_HTTP_PORT(self) -> int:
        return int(
            get_env("WEB_HTTP_PORT", self.DEFAULT_WEB_HTTP_PORT, self.ENV_PREFIX)
        )

    @WEB_HTTP_PORT.setter
    def WEB_HTTP_PORT(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_WEB_HTTP_PORT"] = str(value)

    @property
    def WEB_GUEST_USERNAME(self) -> str:
        return get_env(
            "WEB_GUEST_USERNAME", self.DEFAULT_WEB_GUEST_USERNAME, self.ENV_PREFIX
        )

    @WEB_GUEST_USERNAME.setter
    def WEB_GUEST_USERNAME(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_WEB_GUEST_USERNAME"] = value

    @property
    def WEB_SUPER_ADMIN_USERNAME(self) -> str:
        return get_env(
            "WEB_SUPER_ADMIN_USERNAME",
            self.DEFAULT_WEB_SUPER_ADMIN_USERNAME,
            self.ENV_PREFIX,
        )

    @WEB_SUPER_ADMIN_USERNAME.setter
    def WEB_SUPER_ADMIN_USERNAME(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_WEB_SUPER_ADMIN_USERNAME"] = value

    @property
    def WEB_SUPER_ADMIN_PASSWORD(self) -> str:
        return get_env(
            "WEB_SUPER_ADMIN_PASSWORD",
            self.DEFAULT_WEB_SUPER_ADMIN_PASSWORD,
            self.ENV_PREFIX,
        )

    @WEB_SUPER_ADMIN_PASSWORD.setter
    def WEB_SUPER_ADMIN_PASSWORD(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_WEB_SUPER_ADMIN_PASSWORD"] = value

    @property
    def WEB_ACCESS_TOKEN_COOKIE_NAME(self) -> str:
        return get_env(
            "WEB_ACCESS_TOKEN_COOKIE_NAME",
            self.DEFAULT_WEB_ACCESS_TOKEN_COOKIE_NAME,
            self.ENV_PREFIX,
        )

    @WEB_ACCESS_TOKEN_COOKIE_NAME.setter
    def WEB_ACCESS_TOKEN_COOKIE_NAME(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_WEB_ACCESS_TOKEN_COOKIE_NAME"] = value

    @property
    def WEB_REFRESH_TOKEN_COOKIE_NAME(self) -> str:
        return get_env(
            "WEB_REFRESH_TOKEN_COOKIE_NAME",
            self.DEFAULT_WEB_REFRESH_TOKEN_COOKIE_NAME,
            self.ENV_PREFIX,
        )

    @WEB_REFRESH_TOKEN_COOKIE_NAME.setter
    def WEB_REFRESH_TOKEN_COOKIE_NAME(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_WEB_REFRESH_TOKEN_COOKIE_NAME"] = value

    @property
    def WEB_SECRET_KEY(self) -> str:
        return get_env("WEB_SECRET", self.DEFAULT_WEB_SECRET_KEY, self.ENV_PREFIX)

    @WEB_SECRET_KEY.setter
    def WEB_SECRET_KEY(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_WEB_SECRET"] = value

    @property
    def WEB_ENABLE_AUTH(self) -> bool:
        return to_boolean(
            get_env("WEB_ENABLE_AUTH", self.DEFAULT_WEB_ENABLE_AUTH, self.ENV_PREFIX)
        )

    @WEB_ENABLE_AUTH.setter
    def WEB_ENABLE_AUTH(self, value: bool):
        os.environ[f"{self.ENV_PREFIX}_WEB_ENABLE_AUTH"] = "1" if value else "0"

    @property
    def WEB_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES(self) -> int:
        return int(
            get_env(
                "WEB_ACCESS_TOKEN_EXPIRE_MINUTES",
                self.DEFAULT_WEB_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES,
                self.ENV_PREFIX,
            )
        )

    @WEB_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES.setter
    def WEB_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_WEB_ACCESS_TOKEN_EXPIRE_MINUTES"] = str(value)

    @property
    def WEB_AUTH_REFRESH_TOKEN_EXPIRE_MINUTES(self) -> int:
        return int(
            get_env(
                "WEB_REFRESH_TOKEN_EXPIRE_MINUTES",
                self.DEFAULT_WEB_AUTH_REFRESH_TOKEN_EXPIRE_MINUTES,
                self.ENV_PREFIX,
            )
        )

    @WEB_AUTH_REFRESH_TOKEN_EXPIRE_MINUTES.setter
    def WEB_AUTH_REFRESH_TOKEN_EXPIRE_MINUTES(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_WEB_REFRESH_TOKEN_EXPIRE_MINUTES"] = str(value)

    @property
    def WEB_TITLE(self) -> str:
        return get_env("WEB_TITLE", self.DEFAULT_WEB_TITLE, self.ENV_PREFIX)

    @WEB_TITLE.setter
    def WEB_TITLE(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_WEB_TITLE"] = value

    @property
    def WEB_JARGON(self) -> str:
        return get_env("WEB_JARGON", self.DEFAULT_WEB_JARGON, self.ENV_PREFIX)

    @WEB_JARGON.setter
    def WEB_JARGON(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_WEB_JARGON"] = value

    @property
    def WEB_HOMEPAGE_INTRO(self) -> str:
        return get_env(
            "WEB_HOMEPAGE_INTRO", self.DEFAULT_WEB_HOMEPAGE_INTRO, self.ENV_PREFIX
        )

    @WEB_HOMEPAGE_INTRO.setter
    def WEB_HOMEPAGE_INTRO(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_WEB_HOMEPAGE_INTRO"] = value

    @property
    def ASCII_ART_DIR(self) -> str:
        default = self.DEFAULT_ASCII_ART_DIR
        if default == "":
            default = os.path.join(f".{self.ROOT_GROUP_NAME}", "llm", "prompt")
        return get_env(
            "ASCII_ART_DIR",
            default,
            self.ENV_PREFIX,
        )

    @ASCII_ART_DIR.setter
    def ASCII_ART_DIR(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_ASCII_ART_DIR"] = value

    @property
    def LLM_ASSISTANT_NAME(self) -> str:
        default = self.DEFAULT_LLM_ASSISTANT_NAME
        if default == "":
            default = self.ROOT_GROUP_NAME
        return get_env("LLM_ASSISTANT_NAME", default, self.ENV_PREFIX)

    @LLM_ASSISTANT_NAME.setter
    def LLM_ASSISTANT_NAME(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_LLM_ASSISTANT_NAME"] = value

    @property
    def LLM_ASSISTANT_ASCII_ART(self) -> str:
        return get_env(
            "LLM_ASSISTANT_ASCII_ART",
            self.DEFAULT_LLM_ASSISTANT_ASCII_ART,
            self.ENV_PREFIX,
        )

    @LLM_ASSISTANT_ASCII_ART.setter
    def LLM_ASSISTANT_ASCII_ART(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_LLM_ASSISTANT_ASCII_ART"] = value

    @property
    def LLM_ASSISTANT_JARGON(self) -> str:
        default = self.DEFAULT_LLM_ASSISTANT_JARGON
        if default == "":
            default = self.ROOT_GROUP_DESCRIPTION
        return get_env(
            "LLM_ASSISTANT_JARGON",
            default,
            self.ENV_PREFIX,
        )

    @LLM_ASSISTANT_JARGON.setter
    def LLM_ASSISTANT_JARGON(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_LLM_ASSISTANT_JARGON"] = value

    @property
    def LLM_UI_STYLE_TITLE_BAR(self) -> str:
        return get_env(
            "LLM_UI_STYLE_TITLE_BAR",
            self.DEFAULT_LLM_UI_STYLE_TITLE_BAR,
            self.ENV_PREFIX,
        )

    @LLM_UI_STYLE_TITLE_BAR.setter
    def LLM_UI_STYLE_TITLE_BAR(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_LLM_UI_STYLE_TITLE_BAR"] = value

    @property
    def LLM_UI_STYLE_INFO_BAR(self) -> str:
        return get_env(
            "LLM_UI_STYLE_INFO_BAR", self.DEFAULT_LLM_UI_STYLE_INFO_BAR, self.ENV_PREFIX
        )

    @LLM_UI_STYLE_INFO_BAR.setter
    def LLM_UI_STYLE_INFO_BAR(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_LLM_UI_STYLE_INFO_BAR"] = value

    @property
    def LLM_UI_STYLE_FRAME(self) -> str:
        return get_env(
            "LLM_UI_STYLE_FRAME", self.DEFAULT_LLM_UI_STYLE_FRAME, self.ENV_PREFIX
        )

    @LLM_UI_STYLE_FRAME.setter
    def LLM_UI_STYLE_FRAME(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_LLM_UI_STYLE_FRAME"] = value

    @property
    def LLM_UI_STYLE_FRAME_LABEL(self) -> str:
        return get_env(
            "LLM_UI_STYLE_FRAME_LABEL",
            self.DEFAULT_LLM_UI_STYLE_FRAME_LABEL,
            self.ENV_PREFIX,
        )

    @LLM_UI_STYLE_FRAME_LABEL.setter
    def LLM_UI_STYLE_FRAME_LABEL(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_LLM_UI_STYLE_FRAME_LABEL"] = value

    @property
    def LLM_UI_STYLE_INPUT_FRAME(self) -> str:
        return get_env(
            "LLM_UI_STYLE_INPUT_FRAME",
            self.DEFAULT_LLM_UI_STYLE_INPUT_FRAME,
            self.ENV_PREFIX,
        )

    @LLM_UI_STYLE_INPUT_FRAME.setter
    def LLM_UI_STYLE_INPUT_FRAME(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_LLM_UI_STYLE_INPUT_FRAME"] = value

    @property
    def LLM_UI_STYLE_THINKING(self) -> str:
        return get_env(
            "LLM_UI_STYLE_THINKING", self.DEFAULT_LLM_UI_STYLE_THINKING, self.ENV_PREFIX
        )

    @LLM_UI_STYLE_THINKING.setter
    def LLM_UI_STYLE_THINKING(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_LLM_UI_STYLE_THINKING"] = value

    @property
    def LLM_UI_STYLE_FAINT(self) -> str:
        return get_env(
            "LLM_UI_STYLE_FAINT", self.DEFAULT_LLM_UI_STYLE_FAINT, self.ENV_PREFIX
        )

    @LLM_UI_STYLE_FAINT.setter
    def LLM_UI_STYLE_FAINT(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_LLM_UI_STYLE_FAINT"] = value

    @property
    def LLM_UI_STYLE_OUTPUT_FIELD(self) -> str:
        return get_env(
            "LLM_UI_STYLE_OUTPUT_FIELD",
            self.DEFAULT_LLM_UI_STYLE_OUTPUT_FIELD,
            self.ENV_PREFIX,
        )

    @LLM_UI_STYLE_OUTPUT_FIELD.setter
    def LLM_UI_STYLE_OUTPUT_FIELD(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_LLM_UI_STYLE_OUTPUT_FIELD"] = value

    @property
    def LLM_UI_STYLE_INPUT_FIELD(self) -> str:
        return get_env(
            "LLM_UI_STYLE_INPUT_FIELD",
            self.DEFAULT_LLM_UI_STYLE_INPUT_FIELD,
            self.ENV_PREFIX,
        )

    @LLM_UI_STYLE_INPUT_FIELD.setter
    def LLM_UI_STYLE_INPUT_FIELD(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_LLM_UI_STYLE_INPUT_FIELD"] = value

    @property
    def LLM_UI_STYLE_TEXT(self) -> str:
        return get_env(
            "LLM_UI_STYLE_TEXT", self.DEFAULT_LLM_UI_STYLE_TEXT, self.ENV_PREFIX
        )

    @LLM_UI_STYLE_TEXT.setter
    def LLM_UI_STYLE_TEXT(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_LLM_UI_STYLE_TEXT"] = value

    @property
    def LLM_UI_STYLE_STATUS(self) -> str:
        return get_env(
            "LLM_UI_STYLE_STATUS", self.DEFAULT_LLM_UI_STYLE_STATUS, self.ENV_PREFIX
        )

    @LLM_UI_STYLE_STATUS.setter
    def LLM_UI_STYLE_STATUS(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_LLM_UI_STYLE_STATUS"] = value

    @property
    def LLM_UI_STYLE_BOTTOM_TOOLBAR(self) -> str:
        return get_env(
            "LLM_UI_STYLE_BOTTOM_TOOLBAR",
            self.DEFAULT_LLM_UI_STYLE_BOTTOM_TOOLBAR,
            self.ENV_PREFIX,
        )

    @LLM_UI_STYLE_BOTTOM_TOOLBAR.setter
    def LLM_UI_STYLE_BOTTOM_TOOLBAR(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_LLM_UI_STYLE_BOTTOM_TOOLBAR"] = value

    @property
    def LLM_UI_COMMAND_SUMMARIZE(self) -> list[str]:
        cmd_str = get_env(
            "LLM_UI_COMMAND_SUMMARIZE",
            self.DEFAULT_LLM_UI_COMMAND_SUMMARIZE,
            self.ENV_PREFIX,
        )
        return [cmd.strip() for cmd in cmd_str.split(",") if cmd.strip() != ""]

    @LLM_UI_COMMAND_SUMMARIZE.setter
    def LLM_UI_COMMAND_SUMMARIZE(self, value: list[str]):
        os.environ[f"{self.ENV_PREFIX}_LLM_UI_COMMAND_SUMMARIZE"] = ",".join(value)

    @property
    def LLM_UI_COMMAND_ATTACH(self) -> list[str]:
        cmd_str = get_env(
            "LLM_UI_COMMAND_ATTACH",
            self.DEFAULT_LLM_UI_COMMAND_ATTACH,
            self.ENV_PREFIX,
        )
        return [cmd.strip() for cmd in cmd_str.split(",") if cmd.strip() != ""]

    @LLM_UI_COMMAND_ATTACH.setter
    def LLM_UI_COMMAND_ATTACH(self, value: list[str]):
        os.environ[f"{self.ENV_PREFIX}_LLM_UI_COMMAND_ATTACH"] = ",".join(value)

    @property
    def LLM_UI_COMMAND_EXIT(self) -> list[str]:
        cmd_str = get_env(
            "LLM_UI_COMMAND_EXIT",
            self.DEFAULT_LLM_UI_COMMAND_EXIT,
            self.ENV_PREFIX,
        )
        return [cmd.strip() for cmd in cmd_str.split(",") if cmd.strip() != ""]

    @LLM_UI_COMMAND_EXIT.setter
    def LLM_UI_COMMAND_EXIT(self, value: list[str]):
        os.environ[f"{self.ENV_PREFIX}_LLM_UI_COMMAND_EXIT"] = ",".join(value)

    @property
    def LLM_UI_COMMAND_INFO(self) -> list[str]:
        cmd_str = get_env(
            "LLM_UI_COMMAND_INFO",
            self.DEFAULT_LLM_UI_COMMAND_INFO,
            self.ENV_PREFIX,
        )
        return [cmd.strip() for cmd in cmd_str.split(",") if cmd.strip() != ""]

    @LLM_UI_COMMAND_INFO.setter
    def LLM_UI_COMMAND_INFO(self, value: list[str]):
        os.environ[f"{self.ENV_PREFIX}_LLM_UI_COMMAND_INFO"] = ",".join(value)

    @property
    def LLM_UI_COMMAND_SAVE(self) -> list[str]:
        cmd_str = get_env(
            "LLM_UI_COMMAND_SAVE",
            self.DEFAULT_LLM_UI_COMMAND_SAVE,
            self.ENV_PREFIX,
        )
        return [cmd.strip() for cmd in cmd_str.split(",") if cmd.strip() != ""]

    @LLM_UI_COMMAND_SAVE.setter
    def LLM_UI_COMMAND_SAVE(self, value: list[str]):
        os.environ[f"{self.ENV_PREFIX}_LLM_UI_COMMAND_SAVE"] = ",".join(value)

    @property
    def LLM_UI_COMMAND_LOAD(self) -> list[str]:
        cmd_str = get_env(
            "LLM_UI_COMMAND_LOAD",
            self.DEFAULT_LLM_UI_COMMAND_LOAD,
            self.ENV_PREFIX,
        )
        return [cmd.strip() for cmd in cmd_str.split(",") if cmd.strip() != ""]

    @LLM_UI_COMMAND_LOAD.setter
    def LLM_UI_COMMAND_LOAD(self, value: list[str]):
        os.environ[f"{self.ENV_PREFIX}_LLM_UI_COMMAND_LOAD"] = ",".join(value)

    @property
    def LLM_UI_COMMAND_YOLO_TOGGLE(self) -> list[str]:
        cmd_str = get_env(
            "LLM_UI_COMMAND_YOLO_TOGGLE",
            self.DEFAULT_LLM_UI_COMMAND_YOLO_TOGGLE,
            self.ENV_PREFIX,
        )
        return [cmd.strip() for cmd in cmd_str.split(",") if cmd.strip() != ""]

    @LLM_UI_COMMAND_YOLO_TOGGLE.setter
    def LLM_UI_COMMAND_YOLO_TOGGLE(self, value: list[str]):
        os.environ[f"{self.ENV_PREFIX}_LLM_UI_COMMAND_YOLO_TOGGLE"] = ",".join(value)

    @property
    def LLM_UI_COMMAND_REDIRECT_OUTPUT(self) -> list[str]:
        cmd_str = get_env(
            "LLM_UI_COMMAND_REDIRECT_OUTPUT",
            self.DEFAULT_LLM_UI_COMMAND_REDIRECT_OUTPUT,
            self.ENV_PREFIX,
        )
        return [cmd.strip() for cmd in cmd_str.split(",") if cmd.strip() != ""]

    @LLM_UI_COMMAND_REDIRECT_OUTPUT.setter
    def LLM_UI_COMMAND_REDIRECT_OUTPUT(self, value: list[str]):
        os.environ[f"{self.ENV_PREFIX}_LLM_UI_COMMAND_REDIRECT_OUTPUT"] = ",".join(
            value
        )

    @property
    def LLM_UI_COMMAND_EXEC(self) -> list[str]:
        cmd_str = get_env(
            "LLM_UI_COMMAND_EXEC",
            self.DEFAULT_LLM_UI_COMMAND_EXEC,
            self.ENV_PREFIX,
        )
        return [cmd.strip() for cmd in cmd_str.split(",") if cmd.strip() != ""]

    @LLM_UI_COMMAND_EXEC.setter
    def LLM_UI_COMMAND_EXEC(self, value: list[str]):
        os.environ[f"{self.ENV_PREFIX}_LLM_UI_COMMAND_EXEC"] = ",".join(value)

    @property
    def LLM_HISTORY_DIR(self) -> str:
        default = self.DEFAULT_LLM_HISTORY_DIR
        if default == "":
            default = os.path.expanduser(
                os.path.join("~", f".{self.ROOT_GROUP_NAME}", "llm-history")
            )
        return get_env(
            "LLM_HISTORY_DIR",
            default,
            self.ENV_PREFIX,
        )

    @LLM_HISTORY_DIR.setter
    def LLM_HISTORY_DIR(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_LLM_HISTORY_DIR"] = value

    @property
    def LLM_NOTE_FILE(self) -> str:
        default = self.DEFAULT_LLM_NOTE_FILE
        if default == "":
            default = os.path.expanduser(
                os.path.join("~", f".{self.ROOT_GROUP_NAME}", "notes.json")
            )
        return get_env(
            "LLM_NOTE_FILE",
            default,
            self.ENV_PREFIX,
        )

    @LLM_NOTE_FILE.setter
    def LLM_NOTE_FILE(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_LLM_NOTE_FILE"] = value

    @property
    def LLM_MODEL(self) -> str | None:
        value = get_env("LLM_MODEL", self.DEFAULT_LLM_MODEL, self.ENV_PREFIX)
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
        value = get_env("LLM_BASE_URL", self.DEFAULT_LLM_BASE_URL, self.ENV_PREFIX)
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
        value = get_env("LLM_API_KEY", self.DEFAULT_LLM_API_KEY, self.ENV_PREFIX)
        return None if value == "" else value

    @LLM_API_KEY.setter
    def LLM_API_KEY(self, value: str | None):
        if value is None:
            if f"{self.ENV_PREFIX}_LLM_API_KEY" in os.environ:
                del os.environ[f"{self.ENV_PREFIX}_LLM_API_KEY"]
        else:
            os.environ[f"{self.ENV_PREFIX}_LLM_API_KEY"] = value

    @property
    def LLM_MAX_REQUEST_PER_MINUTE(self) -> int:
        """
        Maximum number of LLM requests allowed per minute.
        Default is conservative to accommodate free-tier LLM providers.
        """
        return int(
            get_env(
                ["LLM_MAX_REQUEST_PER_MINUTE", "LLM_MAX_REQUESTS_PER_MINUTE"],
                self.DEFAULT_LLM_MAX_REQUEST_PER_MINUTE,
                self.ENV_PREFIX,
            )
        )

    @LLM_MAX_REQUEST_PER_MINUTE.setter
    def LLM_MAX_REQUEST_PER_MINUTE(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_LLM_MAX_REQUEST_PER_MINUTE"] = str(value)

    @property
    def LLM_MAX_TOKENS_PER_MINUTE(self) -> int:
        """
        Maximum number of LLM tokens allowed per minute.
        Default is conservative to accommodate free-tier LLM providers.
        """
        return int(
            get_env(
                ["LLM_MAX_TOKEN_PER_MINUTE", "LLM_MAX_TOKENS_PER_MINUTE"],
                self.DEFAULT_LLM_MAX_TOKENS_PER_MINUTE,
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
                self.DEFAULT_LLM_MAX_TOKENS_PER_REQUEST,
                self.ENV_PREFIX,
            )
        )

    @LLM_MAX_TOKENS_PER_REQUEST.setter
    def LLM_MAX_TOKENS_PER_REQUEST(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_LLM_MAX_TOKENS_PER_REQUEST"] = str(value)

    @property
    def LLM_THROTTLE_SLEEP(self) -> float:
        """Number of seconds to sleep when throttling is required."""
        return float(
            get_env(
                "LLM_THROTTLE_SLEEP",
                self.DEFAULT_LLM_THROTTLE_SLEEP,
                self.ENV_PREFIX,
            )
        )

    @LLM_THROTTLE_SLEEP.setter
    def LLM_THROTTLE_SLEEP(self, value: float):
        os.environ[f"{self.ENV_PREFIX}_LLM_THROTTLE_SLEEP"] = str(value)

    @property
    def LLM_HISTORY_SUMMARIZATION_WINDOW(self) -> int:
        return int(
            get_env(
                "LLM_HISTORY_SUMMARIZATION_WINDOW",
                self.DEFAULT_LLM_HISTORY_SUMMARIZATION_WINDOW,
                self.ENV_PREFIX,
            )
        )

    @LLM_HISTORY_SUMMARIZATION_WINDOW.setter
    def LLM_HISTORY_SUMMARIZATION_WINDOW(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_LLM_HISTORY_SUMMARIZATION_WINDOW"] = str(value)

    @property
    def LLM_HISTORY_SUMMARIZATION_TOKEN_THRESHOLD(self) -> int:
        default = self.DEFAULT_LLM_HISTORY_SUMMARIZATION_TOKEN_THRESHOLD
        if default == "":
            default = str(self._get_max_threshold(0.6))

        threshold = int(
            get_env(
                "LLM_HISTORY_SUMMARIZATION_TOKEN_THRESHOLD",
                default,
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
        default = self.DEFAULT_LLM_REPO_ANALYSIS_EXTRACTION_TOKEN_THRESHOLD
        if default == "":
            default = str(self._get_max_threshold(0.4))

        threshold = int(
            get_env(
                "LLM_REPO_ANALYSIS_EXTRACTION_TOKEN_THRESHOLD",
                default,
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
        default = self.DEFAULT_LLM_REPO_ANALYSIS_SUMMARIZATION_TOKEN_THRESHOLD
        if default == "":
            default = str(self._get_max_threshold(0.4))

        threshold = int(
            get_env(
                "LLM_REPO_ANALYSIS_SUMMARIZATION_TOKEN_THRESHOLD",
                default,
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
        default = self.DEFAULT_LLM_FILE_ANALYSIS_TOKEN_THRESHOLD
        if default == "":
            default = str(self._get_max_threshold(0.4))

        threshold = int(
            get_env(
                "LLM_FILE_ANALYSIS_TOKEN_THRESHOLD",
                default,
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

    @property
    def LLM_PROMPT_DIR(self) -> str:
        default = self.DEFAULT_LLM_PROMPT_DIR
        if default == "":
            default = os.path.join(f".{self.ROOT_GROUP_NAME}", "llm", "prompt")
        return get_env(
            "LLM_PROMPT_DIR",
            default,
            self.ENV_PREFIX,
        )

    @LLM_PROMPT_DIR.setter
    def LLM_PROMPT_DIR(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_LLM_PROMPT_DIR"] = value

    def _get_max_threshold(self, factor: float) -> int:
        return get_max_token_threshold(
            factor, self.LLM_MAX_TOKENS_PER_MINUTE, self.LLM_MAX_TOKENS_PER_REQUEST
        )

    @property
    def RAG_EMBEDDING_API_KEY(self) -> str | None:
        value = get_env(
            "RAG_EMBEDDING_API_KEY", self.DEFAULT_RAG_EMBEDDING_API_KEY, self.ENV_PREFIX
        )
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
        value = get_env(
            "RAG_EMBEDDING_BASE_URL",
            self.DEFAULT_RAG_EMBEDDING_BASE_URL,
            self.ENV_PREFIX,
        )
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
        return get_env(
            "RAG_EMBEDDING_MODEL", self.DEFAULT_RAG_EMBEDDING_MODEL, self.ENV_PREFIX
        )

    @RAG_EMBEDDING_MODEL.setter
    def RAG_EMBEDDING_MODEL(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_RAG_EMBEDDING_MODEL"] = value

    @property
    def RAG_CHUNK_SIZE(self) -> int:
        return int(
            get_env("RAG_CHUNK_SIZE", self.DEFAULT_RAG_CHUNK_SIZE, self.ENV_PREFIX)
        )

    @RAG_CHUNK_SIZE.setter
    def RAG_CHUNK_SIZE(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_RAG_CHUNK_SIZE"] = str(value)

    @property
    def RAG_OVERLAP(self) -> int:
        return int(get_env("RAG_OVERLAP", self.DEFAULT_RAG_OVERLAP, self.ENV_PREFIX))

    @RAG_OVERLAP.setter
    def RAG_OVERLAP(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_RAG_OVERLAP"] = str(value)

    @property
    def RAG_MAX_RESULT_COUNT(self) -> int:
        return int(
            get_env(
                "RAG_MAX_RESULT_COUNT",
                self.DEFAULT_RAG_MAX_RESULT_COUNT,
                self.ENV_PREFIX,
            )
        )

    @RAG_MAX_RESULT_COUNT.setter
    def RAG_MAX_RESULT_COUNT(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_RAG_MAX_RESULT_COUNT"] = str(value)

    @property
    def SEARCH_INTERNET_METHOD(self) -> str:
        """Either serpapi or searxng"""
        return get_env(
            "SEARCH_INTERNET_METHOD",
            self.DEFAULT_SEARCH_INTERNET_METHOD,
            self.ENV_PREFIX,
        )

    @SEARCH_INTERNET_METHOD.setter
    def SEARCH_INTERNET_METHOD(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_SEARCH_INTERNET_METHOD"] = value

    @property
    def BRAVE_API_KEY(self) -> str:
        return os.getenv("BRAVE_API_KEY", self.DEFAULT_BRAVE_API_KEY)

    @BRAVE_API_KEY.setter
    def BRAVE_API_KEY(self, value: str):
        os.environ["BRAVE_API_KEY"] = value

    @property
    def BRAVE_API_SAFE(self) -> str:
        return get_env("BRAVE_API_SAFE", self.DEFAULT_BRAVE_API_SAFE, self.ENV_PREFIX)

    @BRAVE_API_SAFE.setter
    def BRAVE_API_SAFE(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_BRAVE_API_SAFE"] = value

    @property
    def BRAVE_API_LANG(self) -> str:
        return get_env("BRAVE_API_LANG", self.DEFAULT_BRAVE_API_LANG, self.ENV_PREFIX)

    @BRAVE_API_LANG.setter
    def BRAVE_API_LANG(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_BRAVE_API_LANG"] = value

    @property
    def SERPAPI_KEY(self) -> str:
        return os.getenv("SERPAPI_KEY", self.DEFAULT_SERPAPI_KEY)

    @SERPAPI_KEY.setter
    def SERPAPI_KEY(self, value: str):
        os.environ["SERPAPI_KEY"] = value

    @property
    def SERPAPI_SAFE(self) -> str:
        return get_env("SERPAPI_SAFE", self.DEFAULT_SERPAPI_SAFE, self.ENV_PREFIX)

    @SERPAPI_SAFE.setter
    def SERPAPI_SAFE(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_SERPAPI_SAFE"] = value

    @property
    def SERPAPI_LANG(self) -> str:
        return get_env("SERPAPI_LANG", self.DEFAULT_SERPAPI_LANG, self.ENV_PREFIX)

    @SERPAPI_LANG.setter
    def SERPAPI_LANG(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_SERPAPI_LANG"] = value

    @property
    def SEARXNG_PORT(self) -> int:
        return int(get_env("SEARXNG_PORT", self.DEFAULT_SEARXNG_PORT, self.ENV_PREFIX))

    @SEARXNG_PORT.setter
    def SEARXNG_PORT(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_SEARXNG_PORT"] = str(value)

    @property
    def SEARXNG_BASE_URL(self) -> str:
        default = self.DEFAULT_SEARXNG_BASE_URL
        if default == "":
            default = f"http://localhost:{self.SEARXNG_PORT}"
        return get_env("SEARXNG_BASE_URL", default, self.ENV_PREFIX)

    @SEARXNG_BASE_URL.setter
    def SEARXNG_BASE_URL(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_SEARXNG_BASE_URL"] = value

    @property
    def SEARXNG_SAFE(self) -> int:
        return int(get_env("SEARXNG_SAFE", self.DEFAULT_SEARXNG_SAFE, self.ENV_PREFIX))

    @SEARXNG_SAFE.setter
    def SEARXNG_SAFE(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_SEARXNG_SAFE"] = str(value)

    @property
    def SEARXNG_LANG(self) -> str:
        return get_env("SEARXNG_LANG", self.DEFAULT_SEARXNG_LANG, self.ENV_PREFIX)

    @SEARXNG_LANG.setter
    def SEARXNG_LANG(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_SEARXNG_LANG"] = value

    @property
    def BANNER(self) -> str:
        return fstring_format(
            get_env("BANNER", self.DEFAULT_BANNER, self.ENV_PREFIX),
            {"VERSION": self.VERSION},
        )

    @BANNER.setter
    def BANNER(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_BANNER"] = value

    @property
    def LLM_SHOW_TOOL_CALL_DETAIL(self) -> bool:
        return to_boolean(
            get_env(
                "LLM_SHOW_TOOL_CALL_DETAIL",
                self.DEFAULT_LLM_SHOW_TOOL_CALL_DETAIL,
                self.ENV_PREFIX,
            )
        )

    @LLM_SHOW_TOOL_CALL_DETAIL.setter
    def LLM_SHOW_TOOL_CALL_DETAIL(self, value: bool):
        os.environ[f"{self.ENV_PREFIX}_LLM_SHOW_TOOL_CALL_DETAIL"] = (
            "1" if value else "0"
        )

    @property
    def LLM_SHOW_TOOL_CALL_RESULT(self) -> bool:
        return to_boolean(
            get_env(
                "LLM_SHOW_TOOL_CALL_RESULT",
                self.DEFAULT_LLM_SHOW_TOOL_CALL_RESULT,
                self.ENV_PREFIX,
            )
        )

    @LLM_SHOW_TOOL_CALL_RESULT.setter
    def LLM_SHOW_TOOL_CALL_RESULT(self, value: bool):
        os.environ[f"{self.ENV_PREFIX}_LLM_SHOW_TOOL_CALL_RESULT"] = (
            "1" if value else "0"
        )

    @property
    def USE_TIKTOKEN(self) -> bool:
        return to_boolean(
            get_env("USE_TIKTOKEN", self.DEFAULT_USE_TIKTOKEN, self.ENV_PREFIX)
        )

    @USE_TIKTOKEN.setter
    def USE_TIKTOKEN(self, value: bool):
        os.environ[f"{self.ENV_PREFIX}_USE_TIKTOKEN"] = "1" if value else "0"

    @property
    def TIKTOKEN_ENCODING_NAME(self) -> str:
        return get_env(
            ["TIKTOKEN_ENCODING", "TIKTOKEN_ENCODING_NAME"],
            self.DEFAULT_TIKTOKEN_ENCODING_NAME,
            self.ENV_PREFIX,
        )

    @TIKTOKEN_ENCODING_NAME.setter
    def TIKTOKEN_ENCODING_NAME(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_TIKTOKEN_ENCODING_NAME"] = value

    @property
    def MCP_CONFIG_FILE(self) -> str:
        return get_env("MCP_CONFIG_FILE", self.DEFAULT_MCP_CONFIG_FILE, self.ENV_PREFIX)

    @MCP_CONFIG_FILE.setter
    def MCP_CONFIG_FILE(self, value: str):
        os.environ[f"{self.ENV_PREFIX}_MCP_CONFIG_FILE"] = value


CFG = Config()
