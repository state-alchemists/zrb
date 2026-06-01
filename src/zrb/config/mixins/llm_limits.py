"""LLM limits: throttle, retries, timeouts, size caps."""

from __future__ import annotations

from zrb.config.env_field import EnvField


class LLMLimitsMixin:
    ENV_PREFIX: str

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
        self.DEFAULT_LLM_MAX_TOOL_RESULT_CHARS: str = "100000"
        self.DEFAULT_LLM_PROJECT_DOC_MAX_CHARS: str = "8000"
        self.DEFAULT_LLM_MAX_COMPLETION_FILES: str = "5000"
        # Image scaling — 1568px is Anthropic's no-extra-cost tier; JPEG q85 is
        # near-lossless for screenshots while halving size vs. PNG re-encode.
        self.DEFAULT_LLM_MAX_IMAGE_DIMENSION: str = "1568"
        self.DEFAULT_LLM_IMAGE_JPEG_QUALITY: str = "85"
        super().__init__()

    LLM_MAX_REQUEST_PER_MINUTE = EnvField(
        int,
        aliases=["LLM_MAX_REQUEST_PER_MINUTE", "LLM_MAX_REQUESTS_PER_MINUTE"],
        doc=(
            "Maximum number of LLM requests allowed per minute.\n\n"
            "Default is conservative to accommodate free-tier LLM providers."
        ),
    )

    # Reads either alias; setter writes the plural TOKENS_ form (kept for
    # backward compatibility with previously written env vars).
    LLM_MAX_TOKEN_PER_MINUTE = EnvField(
        int,
        aliases=["LLM_MAX_TOKEN_PER_MINUTE", "LLM_MAX_TOKENS_PER_MINUTE"],
        write_key="LLM_MAX_TOKENS_PER_MINUTE",
        doc=(
            "Maximum number of LLM tokens allowed per minute.\n\n"
            "Default is conservative to accommodate free-tier LLM providers."
        ),
    )

    LLM_MAX_TOKEN_PER_REQUEST = EnvField(
        int,
        aliases=["LLM_MAX_TOKEN_PER_REQUEST", "LLM_MAX_TOKENS_PER_REQUEST"],
        write_key="LLM_MAX_TOKENS_PER_REQUEST",
        doc="Maximum number of tokens allowed per individual LLM request.",
    )

    LLM_THROTTLE_SLEEP = EnvField(
        float,
        doc="Number of seconds to sleep when throttling is required.",
    )

    # --- Retries ----------------------------------------------------------

    LLM_MAX_CONTEXT_RETRIES = EnvField(
        int, doc="Maximum retries for context-related errors."
    )

    LLM_TOOL_MAX_RETRIES = EnvField(int, doc="Maximum retries for tool calls.")

    LLM_MCP_MAX_RETRIES = EnvField(
        int, doc="Maximum retries for MCP server connections."
    )

    LLM_API_MAX_RETRIES = EnvField(
        int,
        doc=(
            "Max retries for transient provider errors (429, 5xx). "
            "0 or 1 disables retrying."
        ),
    )

    LLM_API_MAX_WAIT = EnvField(
        int,
        doc="Maximum seconds to wait between retries (honors Retry-After header).",
    )

    # --- Timeouts ---------------------------------------------------------

    LLM_SSE_KEEPALIVE_TIMEOUT = EnvField(
        int, doc="Timeout in milliseconds for SSE keepalive messages."
    )

    LLM_REQUEST_TIMEOUT = EnvField(
        int, doc="Default timeout in milliseconds for LLM requests."
    )

    LLM_INPUT_QUEUE_TIMEOUT = EnvField(
        int, doc="Timeout in milliseconds for polling the input queue."
    )

    LLM_SHELL_KILL_WAIT_TIMEOUT = EnvField(
        int, doc="Timeout in milliseconds to wait after killing a shell process."
    )

    LLM_WEB_PAGE_TIMEOUT = EnvField(
        int, doc="Timeout in milliseconds for web page loading (Playwright)."
    )

    LLM_WEB_HTTP_TIMEOUT = EnvField(
        int, doc="Timeout in milliseconds for HTTP requests."
    )

    LLM_MODEL_FETCH_TIMEOUT = EnvField(
        int, doc="Timeout in milliseconds for fetching model lists."
    )

    LLM_GIT_CMD_TIMEOUT = EnvField(int, doc="Timeout in milliseconds for git commands.")

    # --- Size caps --------------------------------------------------------

    LLM_MAX_OUTPUT_CHARS = EnvField(
        int,
        doc="Maximum characters for tool output (shell commands, file reads).",
    )

    LLM_MAX_TOOL_RESULT_CHARS = EnvField(
        int,
        doc=(
            "Global backstop cap (characters) on every tool's model-facing "
            "result, applied after the tool runs. Catches outputs not already "
            "capped by a tool (Grep, AnalyzeCode, web, MCP). 0 disables it; "
            "only the model-facing text is affected, not structured returns."
        ),
    )

    LLM_MAX_IMAGE_DIMENSION = EnvField(
        int,
        doc="Longest-edge cap (pixels) applied to attached images before send.",
    )

    LLM_IMAGE_JPEG_QUALITY = EnvField(
        int,
        doc="JPEG quality (1-95) used when re-encoding photos. Ignored for PNGs.",
    )

    LLM_PROJECT_DOC_MAX_CHARS = EnvField(
        int, doc="Maximum characters for project documentation."
    )

    LLM_MAX_COMPLETION_FILES = EnvField(
        int, doc="Maximum number of files for completion."
    )
