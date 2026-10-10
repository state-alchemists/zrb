"""Session token-usage counters for `BaseUI`, reached as `BaseUI.usage`."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from zrb.llm.agent.types import RequestUsage, RunUsage


class BaseUIUsage:
    """Accumulated session token counters and current context-window size."""

    def __init__(self) -> None:
        self.reset()

    @property
    def session_token_usage(self) -> tuple[int, int]:
        """Accumulated (input, output) tokens across all runs in this session."""
        return self._session_input_tokens, self._session_output_tokens

    @property
    def session_cache_read_tokens(self) -> int:
        """Accumulated cache-read (cache-hit) tokens across the session."""
        return self._session_cache_read_tokens

    @property
    def context_tokens(self) -> int:
        """Tokens in the current context window (last request's input + output)."""
        return self._context_tokens

    def accumulate(
        self, usage: "RunUsage", context_usage: "RequestUsage | None" = None
    ) -> None:
        """Fold one run's usage into session totals and refresh context size.

        `context_usage` is the last request's usage; its `input_tokens` already
        include cache reads and writes (pydantic-ai `AbstractUsage`).
        """
        self._session_input_tokens += getattr(usage, "input_tokens", 0) or 0
        self._session_output_tokens += getattr(usage, "output_tokens", 0) or 0
        self._session_cache_read_tokens += getattr(usage, "cache_read_tokens", 0) or 0
        if context_usage is not None:
            self._context_tokens = (getattr(context_usage, "input_tokens", 0) or 0) + (
                getattr(context_usage, "output_tokens", 0) or 0
            )

    def reset(self) -> None:
        """Zero the session token totals (e.g. when switching conversations)."""
        self._session_input_tokens = 0
        self._session_output_tokens = 0
        self._session_cache_read_tokens = 0
        # Current context-window occupancy; replaced each turn, not summed.
        self._context_tokens = 0
