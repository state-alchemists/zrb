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

    @property
    def ENV_PREFIX(self) -> str:
        return os.getenv("_ZRB_ENV_PREFIX", "ZRB")

    def _getenv(self, env_name: str | list[str], default: str = "") -> str:
        env_name_list = env_name if isinstance(env_name, list) else [env_name]
        for env_name in env_name_list:
            value = os.getenv(f"{self.ENV_PREFIX}_{env_name}", None)
            if value is not None:
                return value
        return default

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
        return self._getenv("SHELL", self._get_current_shell())

    def _get_current_shell(self) -> str:
        if platform.system() == "Windows":
            return "PowerShell"
        current_shell = os.getenv("SHELL", "")
        if current_shell.endswith("zsh"):
            return "zsh"
        return "bash"

    @property
    def DEFAULT_EDITOR(self) -> str:
        return self._getenv("EDITOR", "nano")

    @property
    def DEFAULT_DIFF_EDIT_COMMAND_TPL(self) -> str:
        return self._getenv("DIFF_EDIT_COMMAND", self._get_default_diff_edit_command())

    def _get_default_diff_edit_command(self) -> str:
        editor = self.DEFAULT_EDITOR
        if editor in [
            "code",
            "vscode",
            "vscodium",
            "windsurf",
            "cursor",
            "zed",
            "zeditor",
            "agy",
        ]:
            return f"{editor} --wait --diff {{old}} {{new}}"
        if editor == "emacs":
            return 'emacs --eval \'(ediff-files "{old}" "{new}")\''
        if editor in ["nvim", "vim"]:
            return (
                f"{editor} -d {{old}} {{new}} "
                "-i NONE "
                '-c "wincmd h | set readonly | wincmd l" '
                '-c "highlight DiffAdd cterm=bold ctermbg=22 guibg=#005f00 | highlight DiffChange cterm=bold ctermbg=24 guibg=#005f87 | highlight DiffText ctermbg=21 guibg=#0000af | highlight DiffDelete ctermbg=52 guibg=#5f0000" '  # noqa
                '-c "set showtabline=2 | set tabline=[Instructions]\\ :wqa(save\\ &\\ quit)\\ \\|\\ i/esc(toggle\\ edit\\ mode)" '  # noqa
                '-c "wincmd h | setlocal statusline=OLD\\ FILE" '
                '-c "wincmd l | setlocal statusline=%#StatusBold#NEW\\ FILE\\ :wqa(save\\ &\\ quit)\\ \\|\\ i/esc(toggle\\ edit\\ mode)" '  # noqa
                '-c "autocmd BufWritePost * wqa"'
            )
        return 'vimdiff {old} {new} +"setlocal ro" +"wincmd l" +"autocmd BufWritePost <buffer> qa"'  # noqa

    @property
    def INIT_MODULES(self) -> list[str]:
        init_modules_str = self._getenv("INIT_MODULES", "")
        if init_modules_str != "":
            return [
                module.strip()
                for module in init_modules_str.split(":")
                if module.strip() != ""
            ]
        return []

    @property
    def ROOT_GROUP_NAME(self) -> str:
        return self._getenv("ROOT_GROUP_NAME", "zrb")

    @property
    def ROOT_GROUP_DESCRIPTION(self) -> str:
        return self._getenv("ROOT_GROUP_DESCRIPTION", "Your Automation Powerhouse")

    @property
    def INIT_SCRIPTS(self) -> list[str]:
        init_scripts_str = self._getenv("INIT_SCRIPTS", "")
        if init_scripts_str != "":
            return [
                script.strip()
                for script in init_scripts_str.split(":")
                if script.strip() != ""
            ]
        return []

    @property
    def INIT_FILE_NAME(self) -> str:
        return self._getenv("INIT_FILE_NAME", "zrb_init.py")

    @property
    def LOGGING_LEVEL(self) -> int:
        return self._get_log_level(self._getenv("LOGGING_LEVEL", "WARNING"))

    def _get_log_level(self, level: str) -> int:
        level = level.upper()
        log_levels = {
            "CRITICAL": logging.CRITICAL,  # 50
            "FATAL": logging.CRITICAL,  # 50
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
        return to_boolean(self._getenv("LOAD_BUILTIN", "1"))

    @property
    def WARN_UNRECOMMENDED_COMMAND(self) -> bool:
        return to_boolean(self._getenv("WARN_UNRECOMMENDED_COMMAND", "1"))

    @property
    def SESSION_LOG_DIR(self) -> str:
        return os.getenv(
            "ZRB_SESSION_LOG_DIR", os.path.expanduser(os.path.join("~", ".zrb-session"))
        )

    @property
    def TODO_DIR(self) -> str:
        return self._getenv("TODO_DIR", os.path.expanduser(os.path.join("~", "todo")))

    @property
    def TODO_VISUAL_FILTER(self) -> str:
        return self._getenv("TODO_FILTER", "")

    @property
    def TODO_RETENTION(self) -> str:
        return self._getenv("TODO_RETENTION", "2w")

    @property
    def VERSION(self) -> str:
        custom_version = os.getenv("_ZRB_CUSTOM_VERSION", "")
        if custom_version != "":
            return custom_version
        return metadata.version("zrb")

    @property
    def WEB_CSS_PATH(self) -> list[str]:
        web_css_path_str = self._getenv("WEB_CSS_PATH", "")
        if web_css_path_str != "":
            return [
                path.strip()
                for path in web_css_path_str.split(":")
                if path.strip() != ""
            ]
        return []

    @property
    def WEB_JS_PATH(self) -> list[str]:
        web_js_path_str = self._getenv("WEB_JS_PATH", "")
        if web_js_path_str != "":
            return [
                path.strip()
                for path in web_js_path_str.split(":")
                if path.strip() != ""
            ]
        return []

    @property
    def WEB_FAVICON_PATH(self) -> str:
        return self._getenv("WEB_FAVICON_PATH", "/static/favicon-32x32.png")

    @property
    def WEB_COLOR(self) -> str:
        return self._getenv("WEB_COLOR", "")

    @property
    def WEB_HTTP_PORT(self) -> int:
        return int(self._getenv("WEB_HTTP_PORT", "21213"))

    @property
    def WEB_GUEST_USERNAME(self) -> str:
        return self._getenv("WEB_GUEST_USERNAME", "user")

    @property
    def WEB_SUPER_ADMIN_USERNAME(self) -> str:
        return self._getenv("WEB_SUPER_ADMIN_USERNAME", "admin")

    @property
    def WEB_SUPER_ADMIN_PASSWORD(self) -> str:
        return self._getenv("WEB_SUPER_ADMIN_PASSWORD", "admin")

    @property
    def WEB_ACCESS_TOKEN_COOKIE_NAME(self) -> str:
        return self._getenv("WEB_ACCESS_TOKEN_COOKIE_NAME", "access_token")

    @property
    def WEB_REFRESH_TOKEN_COOKIE_NAME(self) -> str:
        return self._getenv("WEB_REFRESH_TOKEN_COOKIE_NAME", "refresh_token")

    @property
    def WEB_SECRET_KEY(self) -> str:
        return self._getenv("WEB_SECRET", "zrb")

    @property
    def WEB_ENABLE_AUTH(self) -> bool:
        return to_boolean(self._getenv("WEB_ENABLE_AUTH", "0"))

    @property
    def WEB_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES(self) -> int:
        return int(self._getenv("WEB_ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

    @property
    def WEB_AUTH_REFRESH_TOKEN_EXPIRE_MINUTES(self) -> int:
        return int(self._getenv("WEB_REFRESH_TOKEN_EXPIRE_MINUTES", "60"))

    @property
    def WEB_TITLE(self) -> str:
        return self._getenv("WEB_TITLE", "Zrb")

    @property
    def WEB_JARGON(self) -> str:
        return self._getenv("WEB_JARGON", "Your Automation PowerHouse")

    @property
    def WEB_HOMEPAGE_INTRO(self) -> str:
        return self._getenv("WEB_HOMEPAGE_INTRO", "Welcome to Zrb Web Interface")

    @property
    def LLM_MODEL(self) -> str | None:
        value = self._getenv("LLM_MODEL")
        return None if value == "" else value

    @property
    def LLM_BASE_URL(self) -> str | None:
        value = self._getenv("LLM_BASE_URL")
        return None if value == "" else value

    @property
    def LLM_API_KEY(self) -> str | None:
        value = self._getenv("LLM_API_KEY")
        return None if value == "" else value

    @property
    def LLM_MODEL_SMALL(self) -> str | None:
        value = self._getenv("LLM_MODEL_SMALL")
        return None if value == "" else value

    @property
    def LLM_BASE_URL_SMALL(self) -> str | None:
        value = self._getenv("LLM_BASE_URL_SMALL")
        return None if value == "" else value

    @property
    def LLM_API_KEY_SMALL(self) -> str | None:
        value = self._getenv("LLM_API_KEY_SMALL")
        return None if value == "" else value

    @property
    def LLM_SYSTEM_PROMPT(self) -> str | None:
        value = self._getenv("LLM_SYSTEM_PROMPT")
        return None if value == "" else value

    @property
    def LLM_INTERACTIVE_SYSTEM_PROMPT(self) -> str | None:
        value = self._getenv("LLM_INTERACTIVE_SYSTEM_PROMPT")
        return None if value == "" else value

    @property
    def LLM_PERSONA(self) -> str | None:
        value = self._getenv("LLM_PERSONA")
        return None if value == "" else value

    @property
    def LLM_WORKFLOWS(self) -> list[str]:
        """Get a list of LLM workflows from environment variables."""
        workflows = []
        for workflow in self._getenv("LLM_WORKFLOWS", "").split(","):
            workflow = workflow.strip()
            if workflow != "":
                workflows.append(workflow)
        return workflows

    @property
    def LLM_BUILTIN_WORKFLOW_PATHS(self) -> list[str]:
        """Get a list of additional builtin workflow paths from environment variables."""
        builtin_workflow_paths_str = self._getenv(
            ["LLM_BUILTIN_WORFKLOW_PATH", "LLM_BUILTIN_WORKFLOW_PATHS"], ""
        )
        if builtin_workflow_paths_str != "":
            return [
                path.strip()
                for path in builtin_workflow_paths_str.split(":")
                if path.strip() != ""
            ]
        return []

    @property
    def LLM_SPECIAL_INSTRUCTION_PROMPT(self) -> str | None:
        value = self._getenv("LLM_SPECIAL_INSTRUCTION_PROMPT")
        return None if value == "" else value

    @property
    def LLM_SUMMARIZATION_PROMPT(self) -> str | None:
        value = self._getenv("LLM_SUMMARIZATION_PROMPT")
        return None if value == "" else value

    @property
    def LLM_SHOW_TOOL_CALL_RESULT(self) -> bool:
        return to_boolean(self._getenv("LLM_SHOW_TOOL_CALL_RESULT", "false"))

    @property
    def LLM_MAX_REQUESTS_PER_MINUTE(self) -> int:
        """
        Maximum number of LLM requests allowed per minute.
        Default is conservative to accommodate free-tier LLM providers.
        """
        return int(
            self._getenv(
                ["LLM_MAX_REQUEST_PER_MINUTE", "LLM_MAX_REQUESTS_PER_MINUTE"], "60"
            )
        )

    @property
    def LLM_MAX_TOKENS_PER_MINUTE(self) -> int:
        """
        Maximum number of LLM tokens allowed per minute.
        Default is conservative to accommodate free-tier LLM providers.
        """
        return int(
            self._getenv(
                ["LLM_MAX_TOKEN_PER_MINUTE", "LLM_MAX_TOKENS_PER_MINUTE"], "100000"
            )
        )

    @property
    def LLM_MAX_TOKENS_PER_REQUEST(self) -> int:
        """Maximum number of tokens allowed per individual LLM request."""
        return int(
            self._getenv(
                ["LLM_MAX_TOKEN_PER_REQUEST", "LLM_MAX_TOKENS_PER_REQUEST"], "120000"
            )
        )

    @property
    def LLM_MAX_TOKENS_PER_TOOL_CALL_RESULT(self) -> int:
        """Maximum number of tokens allowed per tool call result."""
        return int(
            self._getenv(
                [
                    "LLM_MAX_TOKEN_PER_TOOL_CALL_RESULT",
                    "LLM_MAX_TOKENS_PER_TOOL_CALL_RESULT",
                ],
                str(self._get_max_threshold(0.4)),
            )
        )

    @property
    def LLM_THROTTLE_SLEEP(self) -> float:
        """Number of seconds to sleep when throttling is required."""
        return float(self._getenv("LLM_THROTTLE_SLEEP", "5.0"))

    @property
    def LLM_YOLO_MODE(self) -> bool | list[str]:
        str_val = self._getenv("LLM_YOLO_MODE", "false")
        try:
            return to_boolean(str_val)
        except Exception:
            return [val.strip() for val in str_val.split(",") if val.strip() != ""]

    @property
    def LLM_SUMMARIZE_HISTORY(self) -> bool:
        return to_boolean(self._getenv("LLM_SUMMARIZE_HISTORY", "true"))

    @property
    def LLM_HISTORY_SUMMARIZATION_TOKEN_THRESHOLD(self) -> int:
        threshold = int(
            self._getenv(
                "LLM_HISTORY_SUMMARIZATION_TOKEN_THRESHOLD",
                str(self._get_max_threshold(0.6)),
            )
        )
        return self._limit_token_threshold(threshold, 0.6)

    @property
    def LLM_REPO_ANALYSIS_EXTRACTION_TOKEN_THRESHOLD(self) -> int:
        threshold = int(
            self._getenv(
                "LLM_REPO_ANALYSIS_EXTRACTION_TOKEN_THRESHOLD",
                str(self._get_max_threshold(0.4)),
            )
        )
        return self._limit_token_threshold(threshold, 0.4)

    @property
    def LLM_REPO_ANALYSIS_SUMMARIZATION_TOKEN_THRESHOLD(self) -> int:
        threshold = int(
            self._getenv(
                "LLM_REPO_ANALYSIS_SUMMARIZATION_TOKEN_THRESHOLD",
                str(self._get_max_threshold(0.4)),
            )
        )
        return self._limit_token_threshold(threshold, 0.4)

    @property
    def LLM_FILE_ANALYSIS_TOKEN_THRESHOLD(self) -> int:
        threshold = int(
            self._getenv(
                "LLM_FILE_ANALYSIS_TOKEN_THRESHOLD", str(self._get_max_threshold(0.4))
            )
        )
        return self._limit_token_threshold(threshold, 0.4)

    def _limit_token_threshold(self, threshold: int, factor: float) -> int:
        return min(threshold, self._get_max_threshold(factor))

    def _get_max_threshold(self, factor: float) -> int:
        return round(
            factor
            * min(self.LLM_MAX_TOKENS_PER_MINUTE, self.LLM_MAX_TOKENS_PER_REQUEST)
        )

    @property
    def LLM_FILE_EXTRACTOR_SYSTEM_PROMPT(self) -> str:
        return self._getenv(
            "LLM_FILE_EXTRACTOR_SYSTEM_PROMPT",
            self._get_internal_default_prompt("file_extractor_system_prompt"),
        )

    @property
    def LLM_REPO_EXTRACTOR_SYSTEM_PROMPT(self) -> str:
        return self._getenv(
            "LLM_REPO_EXTRACTOR_SYSTEM_PROMPT",
            self._get_internal_default_prompt("repo_extractor_system_prompt"),
        )

    @property
    def LLM_REPO_SUMMARIZER_SYSTEM_PROMPT(self) -> str:
        return self._getenv(
            "LLM_REPO_SUMMARIZER_SYSTEM_PROMPT",
            self._get_internal_default_prompt("repo_summarizer_system_prompt"),
        )

    @property
    def LLM_HISTORY_DIR(self) -> str:
        return self._getenv(
            "LLM_HISTORY_DIR",
            os.path.expanduser(os.path.join("~", ".zrb-llm-history")),
        )

    @property
    def LLM_ALLOW_ACCESS_LOCAL_FILE(self) -> bool:
        return to_boolean(self._getenv("LLM_ALLOW_ACCESS_LOCAL_FILE", "1"))

    @property
    def LLM_ALLOW_ANALYZE_FILE(self) -> bool:
        return to_boolean(self._getenv("LLM_ALLOW_ANALYZE_LOCAL_FILE", "1"))

    @property
    def LLM_ALLOW_ANALYZE_REPO(self) -> bool:
        return to_boolean(self._getenv("LLM_ALLOW_ANALYZE_REPO", "1"))

    @property
    def LLM_ALLOW_ACCESS_SHELL(self) -> bool:
        return to_boolean(self._getenv("LLM_ALLOW_ACCESS_SHELL", "1"))

    @property
    def LLM_ALLOW_OPEN_WEB_PAGE(self) -> bool:
        return to_boolean(self._getenv("LLM_ALLOW_OPEN_WEB_PAGE", "1"))

    @property
    def LLM_ALLOW_SEARCH_INTERNET(self) -> bool:
        return to_boolean(self._getenv("LLM_ALLOW_SEARCH_INTERNET", "1"))

    @property
    def LLM_ALLOW_GET_CURRENT_LOCATION(self) -> bool:
        return to_boolean(self._getenv("LLM_ALLOW_GET_CURRENT_LOCATION", "1"))

    @property
    def LLM_ALLOW_GET_CURRENT_WEATHER(self) -> bool:
        return to_boolean(self._getenv("LLM_ALLOW_GET_CURRENT_WEATHER", "1"))

    @property
    def RAG_EMBEDDING_API_KEY(self) -> str | None:
        value = self._getenv("RAG_EMBEDDING_API_KEY")
        return None if value == "" else value

    @property
    def RAG_EMBEDDING_BASE_URL(self) -> str | None:
        value = self._getenv("RAG_EMBEDDING_BASE_URL")
        return None if value == "" else value

    @property
    def RAG_EMBEDDING_MODEL(self) -> str:
        return self._getenv("RAG_EMBEDDING_MODEL", "text-embedding-ada-002")

    @property
    def RAG_CHUNK_SIZE(self) -> int:
        return int(self._getenv("RAG_CHUNK_SIZE", "1024"))

    @property
    def RAG_OVERLAP(self) -> int:
        return int(self._getenv("RAG_OVERLAP", "128"))

    @property
    def RAG_MAX_RESULT_COUNT(self) -> int:
        return int(self._getenv("RAG_MAX_RESULT_COUNT", "5"))

    @property
    def SEARCH_INTERNET_METHOD(self) -> str:
        """Either serpapi or searxng"""
        return self._getenv("SEARCH_INTERNET_METHOD", "serpapi")

    @property
    def BRAVE_API_KEY(self) -> str:
        return os.getenv("BRAVE_API_KEY", "")

    @property
    def BRAVE_API_SAFE(self) -> str:
        return self._getenv("BRAVE_API_SAFE", "off")

    @property
    def BRAVE_API_LANG(self) -> str:
        return self._getenv("BRAVE_API_LANG", "en")

    @property
    def SERPAPI_KEY(self) -> str:
        return os.getenv("SERPAPI_KEY", "")

    @property
    def SERPAPI_SAFE(self) -> str:
        return self._getenv("SERPAPI_SAFE", "off")

    @property
    def SERPAPI_LANG(self) -> str:
        return self._getenv("SERPAPI_LANG", "en")

    @property
    def SEARXNG_PORT(self) -> int:
        return int(self._getenv("SEARXNG_PORT", "8080"))

    @property
    def SEARXNG_BASE_URL(self) -> str:
        return self._getenv("SEARXNG_BASE_URL", f"http://localhost:{self.SEARXNG_PORT}")

    @property
    def SEARXNG_SAFE(self) -> int:
        return int(self._getenv("SEARXNG_SAFE", "0"))

    @property
    def SEARXNG_LANG(self) -> str:
        return self._getenv("SEARXNG_LANG", "en")

    @property
    def BANNER(self) -> str:
        return fstring_format(
            self._getenv("BANNER", _DEFAULT_BANNER),
            {"VERSION": self.VERSION},
        )

    @property
    def LLM_CONTEXT_FILE(self) -> str:
        return self._getenv("LLM_CONTEXT_FILE", "ZRB.md")

    @property
    def USE_TIKTOKEN(self) -> bool:
        return to_boolean(self._getenv("USE_TIKTOKEN", "true"))

    @property
    def TIKTOKEN_ENCODING_NAME(self) -> str:
        return self._getenv("TIKTOKEN_ENCODING_NAME", "cl100k_base")


CFG = Config()
