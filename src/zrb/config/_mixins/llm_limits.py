"""LLM limits: throttle, retries, timeouts, size caps."""

from __future__ import annotations

import os

from zrb.config.helper import get_env


class LLMLimitsMixin:
    def __init__(self):
        self.DEFAULT_LLM_MAX_REQUEST_PER_MINUTE: str = "60"
        self.DEFAULT_LLM_MAX_TOKEN_PER_MINUTE: str = "128000"
        self.DEFAULT_LLM_MAX_TOKEN_PER_REQUEST: str = "128000"
        self.DEFAULT_LLM_THROTTLE_SLEEP: str = "1.0"
        self.DEFAULT_LLM_MAX_CONTEXT_RETRIES: str = "5"
        self.DEFAULT_LLM_TOOL_MAX_RETRIES: str = "3"
        self.DEFAULT_LLM_MCP_MAX_RETRIES: str = "3"
        self.DEFAULT_LLM_API_MAX_RETRIES: str = "3"
        self.DEFAULT_LLM_API_MAX_WAIT: str = "60"
        self.DEFAULT_LLM_SSE_KEEPALIVE_TIMEOUT: str = "60000"
        self.DEFAULT_LLM_REQUEST_TIMEOUT: str = "300000"
        self.DEFAULT_LLM_INPUT_QUEUE_TIMEOUT: str = "500"
        self.DEFAULT_LLM_SHELL_KILL_WAIT_TIMEOUT: str = "5000"
        self.DEFAULT_LLM_WEB_PAGE_TIMEOUT: str = "30000"
        self.DEFAULT_LLM_WEB_HTTP_TIMEOUT: str = "30000"
        self.DEFAULT_LLM_MODEL_FETCH_TIMEOUT: str = "5000"
        self.DEFAULT_LLM_GIT_CMD_TIMEOUT: str = "1000"
        self.DEFAULT_LLM_MAX_OUTPUT_CHARS: str = "100000"
        self.DEFAULT_LLM_PROJECT_DOC_MAX_CHARS: str = "8000"
        self.DEFAULT_LLM_MAX_COMPLETION_FILES: str = "5000"
        super().__init__()

    @property
    def LLM_MAX_REQUEST_PER_MINUTE(self) -> int:
        """Maximum number of LLM requests allowed per minute.

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
    def LLM_MAX_TOKEN_PER_MINUTE(self) -> int:
        """Maximum number of LLM tokens allowed per minute.

        Default is conservative to accommodate free-tier LLM providers.
        """
        return int(
            get_env(
                ["LLM_MAX_TOKEN_PER_MINUTE", "LLM_MAX_TOKENS_PER_MINUTE"],
                self.DEFAULT_LLM_MAX_TOKEN_PER_MINUTE,
                self.ENV_PREFIX,
            )
        )

    @LLM_MAX_TOKEN_PER_MINUTE.setter
    def LLM_MAX_TOKEN_PER_MINUTE(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_LLM_MAX_TOKENS_PER_MINUTE"] = str(value)

    @property
    def LLM_MAX_TOKEN_PER_REQUEST(self) -> int:
        """Maximum number of tokens allowed per individual LLM request."""
        return int(
            get_env(
                ["LLM_MAX_TOKEN_PER_REQUEST", "LLM_MAX_TOKENS_PER_REQUEST"],
                self.DEFAULT_LLM_MAX_TOKEN_PER_REQUEST,
                self.ENV_PREFIX,
            )
        )

    @LLM_MAX_TOKEN_PER_REQUEST.setter
    def LLM_MAX_TOKEN_PER_REQUEST(self, value: int):
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

    # --- Retries ----------------------------------------------------------

    @property
    def LLM_MAX_CONTEXT_RETRIES(self) -> int:
        """Maximum retries for context-related errors."""
        return int(
            get_env(
                "LLM_MAX_CONTEXT_RETRIES",
                self.DEFAULT_LLM_MAX_CONTEXT_RETRIES,
                self.ENV_PREFIX,
            )
        )

    @LLM_MAX_CONTEXT_RETRIES.setter
    def LLM_MAX_CONTEXT_RETRIES(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_LLM_MAX_CONTEXT_RETRIES"] = str(value)

    @property
    def LLM_TOOL_MAX_RETRIES(self) -> int:
        """Maximum retries for tool calls."""
        return int(
            get_env(
                "LLM_TOOL_MAX_RETRIES",
                self.DEFAULT_LLM_TOOL_MAX_RETRIES,
                self.ENV_PREFIX,
            )
        )

    @LLM_TOOL_MAX_RETRIES.setter
    def LLM_TOOL_MAX_RETRIES(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_LLM_TOOL_MAX_RETRIES"] = str(value)

    @property
    def LLM_MCP_MAX_RETRIES(self) -> int:
        """Maximum retries for MCP server connections."""
        return int(
            get_env(
                "LLM_MCP_MAX_RETRIES",
                self.DEFAULT_LLM_MCP_MAX_RETRIES,
                self.ENV_PREFIX,
            )
        )

    @LLM_MCP_MAX_RETRIES.setter
    def LLM_MCP_MAX_RETRIES(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_LLM_MCP_MAX_RETRIES"] = str(value)

    @property
    def LLM_API_MAX_RETRIES(self) -> int:
        """Max retries for transient provider errors (429, 5xx). 0 or 1 disables retrying."""
        return int(
            get_env(
                "LLM_API_MAX_RETRIES",
                self.DEFAULT_LLM_API_MAX_RETRIES,
                self.ENV_PREFIX,
            )
        )

    @LLM_API_MAX_RETRIES.setter
    def LLM_API_MAX_RETRIES(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_LLM_API_MAX_RETRIES"] = str(value)

    @property
    def LLM_API_MAX_WAIT(self) -> int:
        """Maximum seconds to wait between retries (honors Retry-After header)."""
        return int(
            get_env(
                "LLM_API_MAX_WAIT",
                self.DEFAULT_LLM_API_MAX_WAIT,
                self.ENV_PREFIX,
            )
        )

    @LLM_API_MAX_WAIT.setter
    def LLM_API_MAX_WAIT(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_LLM_API_MAX_WAIT"] = str(value)

    # --- Timeouts ---------------------------------------------------------

    @property
    def LLM_SSE_KEEPALIVE_TIMEOUT(self) -> int:
        """Timeout in milliseconds for SSE keepalive messages."""
        return int(
            get_env(
                "LLM_SSE_KEEPALIVE_TIMEOUT",
                self.DEFAULT_LLM_SSE_KEEPALIVE_TIMEOUT,
                self.ENV_PREFIX,
            )
        )

    @LLM_SSE_KEEPALIVE_TIMEOUT.setter
    def LLM_SSE_KEEPALIVE_TIMEOUT(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_LLM_SSE_KEEPALIVE_TIMEOUT"] = str(value)

    @property
    def LLM_REQUEST_TIMEOUT(self) -> int:
        """Default timeout in milliseconds for LLM requests."""
        return int(
            get_env(
                "LLM_REQUEST_TIMEOUT",
                self.DEFAULT_LLM_REQUEST_TIMEOUT,
                self.ENV_PREFIX,
            )
        )

    @LLM_REQUEST_TIMEOUT.setter
    def LLM_REQUEST_TIMEOUT(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_LLM_REQUEST_TIMEOUT"] = str(value)

    @property
    def LLM_INPUT_QUEUE_TIMEOUT(self) -> int:
        """Timeout in milliseconds for polling the input queue."""
        return int(
            get_env(
                "LLM_INPUT_QUEUE_TIMEOUT",
                self.DEFAULT_LLM_INPUT_QUEUE_TIMEOUT,
                self.ENV_PREFIX,
            )
        )

    @LLM_INPUT_QUEUE_TIMEOUT.setter
    def LLM_INPUT_QUEUE_TIMEOUT(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_LLM_INPUT_QUEUE_TIMEOUT"] = str(value)

    @property
    def LLM_SHELL_KILL_WAIT_TIMEOUT(self) -> int:
        """Timeout in milliseconds to wait after killing a shell process."""
        return int(
            get_env(
                "LLM_SHELL_KILL_WAIT_TIMEOUT",
                self.DEFAULT_LLM_SHELL_KILL_WAIT_TIMEOUT,
                self.ENV_PREFIX,
            )
        )

    @LLM_SHELL_KILL_WAIT_TIMEOUT.setter
    def LLM_SHELL_KILL_WAIT_TIMEOUT(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_LLM_SHELL_KILL_WAIT_TIMEOUT"] = str(value)

    @property
    def LLM_WEB_PAGE_TIMEOUT(self) -> int:
        """Timeout in milliseconds for web page loading (Playwright)."""
        return int(
            get_env(
                "LLM_WEB_PAGE_TIMEOUT",
                self.DEFAULT_LLM_WEB_PAGE_TIMEOUT,
                self.ENV_PREFIX,
            )
        )

    @LLM_WEB_PAGE_TIMEOUT.setter
    def LLM_WEB_PAGE_TIMEOUT(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_LLM_WEB_PAGE_TIMEOUT"] = str(value)

    @property
    def LLM_WEB_HTTP_TIMEOUT(self) -> int:
        """Timeout in milliseconds for HTTP requests."""
        return int(
            get_env(
                "LLM_WEB_HTTP_TIMEOUT",
                self.DEFAULT_LLM_WEB_HTTP_TIMEOUT,
                self.ENV_PREFIX,
            )
        )

    @LLM_WEB_HTTP_TIMEOUT.setter
    def LLM_WEB_HTTP_TIMEOUT(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_LLM_WEB_HTTP_TIMEOUT"] = str(value)

    @property
    def LLM_MODEL_FETCH_TIMEOUT(self) -> int:
        """Timeout in milliseconds for fetching model lists."""
        return int(
            get_env(
                "LLM_MODEL_FETCH_TIMEOUT",
                self.DEFAULT_LLM_MODEL_FETCH_TIMEOUT,
                self.ENV_PREFIX,
            )
        )

    @LLM_MODEL_FETCH_TIMEOUT.setter
    def LLM_MODEL_FETCH_TIMEOUT(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_LLM_MODEL_FETCH_TIMEOUT"] = str(value)

    @property
    def LLM_GIT_CMD_TIMEOUT(self) -> int:
        """Timeout in milliseconds for git commands."""
        return int(
            get_env(
                "LLM_GIT_CMD_TIMEOUT",
                self.DEFAULT_LLM_GIT_CMD_TIMEOUT,
                self.ENV_PREFIX,
            )
        )

    @LLM_GIT_CMD_TIMEOUT.setter
    def LLM_GIT_CMD_TIMEOUT(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_LLM_GIT_CMD_TIMEOUT"] = str(value)

    # --- Size caps --------------------------------------------------------

    @property
    def LLM_MAX_OUTPUT_CHARS(self) -> int:
        """Maximum characters for tool output (shell commands, file reads)."""
        return int(
            get_env(
                "LLM_MAX_OUTPUT_CHARS",
                self.DEFAULT_LLM_MAX_OUTPUT_CHARS,
                self.ENV_PREFIX,
            )
        )

    @LLM_MAX_OUTPUT_CHARS.setter
    def LLM_MAX_OUTPUT_CHARS(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_LLM_MAX_OUTPUT_CHARS"] = str(value)

    @property
    def LLM_PROJECT_DOC_MAX_CHARS(self) -> int:
        """Maximum characters for project documentation."""
        return int(
            get_env(
                "LLM_PROJECT_DOC_MAX_CHARS",
                self.DEFAULT_LLM_PROJECT_DOC_MAX_CHARS,
                self.ENV_PREFIX,
            )
        )

    @LLM_PROJECT_DOC_MAX_CHARS.setter
    def LLM_PROJECT_DOC_MAX_CHARS(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_LLM_PROJECT_DOC_MAX_CHARS"] = str(value)

    @property
    def LLM_MAX_COMPLETION_FILES(self) -> int:
        """Maximum number of files for completion."""
        return int(
            get_env(
                "LLM_MAX_COMPLETION_FILES",
                self.DEFAULT_LLM_MAX_COMPLETION_FILES,
                self.ENV_PREFIX,
            )
        )

    @LLM_MAX_COMPLETION_FILES.setter
    def LLM_MAX_COMPLETION_FILES(self, value: int):
        os.environ[f"{self.ENV_PREFIX}_LLM_MAX_COMPLETION_FILES"] = str(value)
