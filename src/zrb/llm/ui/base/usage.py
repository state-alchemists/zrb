"""Session token-usage counters for `BaseUI`.

Self-contained: unlike `BaseUIReplay`/`BaseUISystemInfo`, this part reads and
writes only its own counters — `accumulate`/`reset` take everything they need
as arguments — so it holds no reference back to `BaseUI`. Composed into
`BaseUI` as `self._base_usage`, reached through the owner's public delegators
(`accumulate_usage`, `session_token_usage`, `session_cache_read_tokens`,
`context_tokens`, `reset_session_token_usage`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from zrb.llm.agent.types import RequestUsage, RunUsage


class BaseUIUsage:
    """Accumulated session token counters and current context-window size."""

    def __init__(self) -> None:
        self._session_input_tokens = 0
        self._session_output_tokens = 0
        self._session_cache_read_tokens = 0
        # Occupancy of the current context window = the last request's prompt
        # size. Unlike the session totals it does not accumulate; it tracks the
        # latest turn and drops after summarization.
        self._context_tokens = 0

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
        """Tokens occupying the current context window (last request's input +
        output — the assistant's reply is now in history and re-sent next
        turn)."""
        return self._context_tokens

    def accumulate(
        self, usage: "RunUsage", context_usage: "RequestUsage | None" = None
    ) -> None:
        """Fold one run's usage into session totals and refresh context size.

        `usage` is the whole-run `RunUsage` (accumulated, for billing). Session
        input/output only grow. `context_usage` is the *last request's*
        `RequestUsage`; current window occupancy is its `input_tokens` (the
        prompt sent — already inclusive of cache reads and writes, per
        pydantic-ai's `AbstractUsage` contract) plus its `output_tokens` (the
        reply, now appended to history). This replaces, not accumulates.
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
        self._context_tokens = 0
