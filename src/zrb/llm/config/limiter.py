import asyncio
import json
import time
from collections import deque
from typing import Any, Callable

from zrb.config.config import CFG


class LLMLimiter:
    """
    Manages LLM constraints: Context Window (Pruning) and Rate Limits (Throttling).
    Designed as a singleton to share limits across tasks.
    """

    def __init__(self):
        # Sliding window logs
        self._request_log: deque[float] = deque()
        self._token_log: deque[tuple[float, int]] = deque()

        # Internal overrides
        self._max_requests_per_minute: int | None = None
        self._max_tokens_per_minute: int | None = None
        self._max_tokens_per_request: int | None = None
        self._throttle_check_interval: float | None = None

    # --- Configuration Properties ---

    @property
    def max_requests_per_minute(self) -> int:
        if self._max_requests_per_minute is not None:
            return self._max_requests_per_minute
        return getattr(CFG, "LLM_MAX_REQUESTS_PER_MINUTE", None) or 60

    @max_requests_per_minute.setter
    def max_requests_per_minute(self, value: int):
        self._max_requests_per_minute = value

    @property
    def max_tokens_per_minute(self) -> int:
        if self._max_tokens_per_minute is not None:
            return self._max_tokens_per_minute
        return getattr(CFG, "LLM_MAX_TOKENS_PER_MINUTE", None) or 100_000

    @max_tokens_per_minute.setter
    def max_tokens_per_minute(self, value: int):
        self._max_tokens_per_minute = value

    @property
    def max_tokens_per_request(self) -> int:
        if self._max_tokens_per_request is not None:
            return self._max_tokens_per_request
        return getattr(CFG, "LLM_MAX_TOKENS_PER_REQUEST", None) or 16_000

    @max_tokens_per_request.setter
    def max_tokens_per_request(self, value: int):
        self._max_tokens_per_request = value

    @property
    def throttle_check_interval(self) -> float:
        if self._throttle_check_interval is not None:
            return self._throttle_check_interval
        return getattr(CFG, "LLM_THROTTLE_SLEEP", None) or 0.1

    @throttle_check_interval.setter
    def throttle_check_interval(self, value: float):
        self._throttle_check_interval = value

    @property
    def use_tiktoken(self) -> bool:
        return getattr(CFG, "USE_TIKTOKEN", False)

    @property
    def tiktoken_encoding(self) -> str:
        return getattr(CFG, "TIKTOKEN_ENCODING_NAME", "cl100k_base")

    # --- Public API ---

    def fit_context_window(self, history: list[Any], new_message: Any) -> list[Any]:
        """
        Prunes the history (removing oldest turns) so that 'history + new_message'
        fits within 'max_tokens_per_request'.
        Ensures strict tool call pairing by removing full conversation turns.
        """
        if not history:
            return history

        # Import message types locally to avoid circular deps or startup cost
        try:
            from pydantic_ai.messages import (
                ModelRequest,
                ToolReturnPart,
                UserPromptPart,
            )
        except ImportError:
            # Fallback if pydantic_ai is not installed (unlikely in context)
            return []

        def is_turn_start(msg: Any) -> bool:
            """Identify start of a new user interaction (User Prompt without Tool Return)."""
            if not isinstance(msg, ModelRequest):
                return False
            has_user = any(isinstance(p, UserPromptPart) for p in msg.parts)
            has_return = any(isinstance(p, ToolReturnPart) for p in msg.parts)
            return has_user and not has_return

        new_msg_tokens = self._count_tokens(new_message)
        if new_msg_tokens > self.max_tokens_per_request:
            return []

        pruned_history = list(history)

        while pruned_history:
            history_tokens = self._count_tokens(pruned_history)
            total_tokens = history_tokens + new_msg_tokens

            if total_tokens <= self.max_tokens_per_request:
                break

            # Pruning Strategy: Find the start of the *next* turn and cut everything before it.
            # We start searching from index 1 because removing index 0 (current start) is the goal.
            next_turn_index = -1
            for i in range(1, len(pruned_history)):
                if is_turn_start(pruned_history[i]):
                    next_turn_index = i
                    break

            if next_turn_index != -1:
                # Remove everything up to the next turn
                pruned_history = pruned_history[next_turn_index:]
            else:
                # No subsequent turns found.
                # This implies the history contains only one (potentially long) turn or partial fragments.
                # To satisfy the limit, we must clear the history entirely.
                pruned_history = []

        return pruned_history

    async def acquire(self, content: Any, notifier: Callable[[str], Any] | None = None):
        """
        Acquires permission to proceed with the given content.
        Calculates token count internally and waits if rate limits are exceeded.
        """
        # Calculate tokens once
        estimated_tokens = self._count_tokens(content)

        # 1. Prune logs older than 60 seconds
        self._prune_logs()

        # 2. Check limits loop
        notified = False
        while not self._can_proceed(estimated_tokens):
            wait_time = self._calculate_wait_time(estimated_tokens)
            reason = self._get_limit_reason(estimated_tokens)

            if notifier:
                msg = f"Rate Limit Reached: {reason}. Waiting {wait_time:.1f}s..."
                # Only notify once or if status changes? Simple is better.
                notifier(msg)
                notified = True

            await asyncio.sleep(self.throttle_check_interval)
            self._prune_logs()

        if notified and notifier:
            notifier("")  # Clear status

        # 3. Record usage
        now = time.time()
        self._request_log.append(now)
        self._token_log.append((now, estimated_tokens))

    def count_tokens(self, content: Any) -> int:
        """Public alias for internal counter."""
        return self._count_tokens(content)

    # --- Internal Helpers ---

    def _count_tokens(self, content: Any) -> int:
        text = self._to_str(content)
        if self.use_tiktoken:
            try:
                import tiktoken

                enc = tiktoken.get_encoding(self.tiktoken_encoding)
                return len(enc.encode(text))
            except ImportError:
                pass
        # Fallback approximation (char/4)
        return len(text) // 4

    def _to_str(self, content: Any) -> str:
        if isinstance(content, str):
            return content
        try:
            return json.dumps(content, default=str)
        except Exception:
            return str(content)

    def _prune_logs(self):
        now = time.time()
        window_start = now - 60

        while self._request_log and self._request_log[0] < window_start:
            self._request_log.popleft()

        while self._token_log and self._token_log[0][0] < window_start:
            self._token_log.popleft()

    def _can_proceed(self, tokens: int) -> bool:
        requests_ok = len(self._request_log) < self.max_requests_per_minute

        current_tokens = sum(t for _, t in self._token_log)
        tokens_ok = (current_tokens + tokens) <= self.max_tokens_per_minute

        return requests_ok and tokens_ok

    def _get_limit_reason(self, tokens: int) -> str:
        if len(self._request_log) >= self.max_requests_per_minute:
            return f"Max Requests ({self.max_requests_per_minute}/min)"
        return f"Max Tokens ({self.max_tokens_per_minute}/min)"

    def _calculate_wait_time(self, tokens: int) -> float:
        now = time.time()
        # Default wait
        wait = 1.0

        # If request limit hit, wait until oldest request expires
        if len(self._request_log) >= self.max_requests_per_minute:
            oldest = self._request_log[0]
            wait = max(0.1, 60 - (now - oldest))

        # If token limit hit, wait until enough tokens expire
        current_tokens = sum(t for _, t in self._token_log)
        if current_tokens + tokens > self.max_tokens_per_minute:
            needed = (current_tokens + tokens) - self.max_tokens_per_minute
            freed = 0
            for ts, count in self._token_log:
                freed += count
                if freed >= needed:
                    wait = max(wait, 60 - (now - ts))
                    break

        return wait


llm_limiter = LLMLimiter()
