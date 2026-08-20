import asyncio
import time
from collections import deque
from typing import Any, Callable

from zrb.config.config import CFG
from zrb.util.cli.style import stylize_info


def is_turn_start(msg: Any) -> bool:
    """Identify start of a new user interaction (User Prompt without Tool Return)."""
    # lazy: heavy third-party
    from pydantic_ai.messages import ModelRequest, ToolReturnPart, UserPromptPart

    if not isinstance(msg, ModelRequest):
        return False
    # In pydantic_ai, ModelRequest parts can be list of various parts
    has_user = any(isinstance(p, UserPromptPart) for p in msg.parts)
    has_return = any(isinstance(p, ToolReturnPart) for p in msg.parts)
    return has_user and not has_return


class LLMLimiter:
    """
    Manages LLM constraints: Context Window (Pruning) and Rate Limits (Throttling).
    Designed as a singleton to share limits across tasks.
    """

    def __init__(self):
        # Sliding window logs
        self.request_log: deque[float] = deque()
        self.token_log: deque[tuple[float, int]] = deque()

        # Internal overrides
        self._max_request_per_minute: int | None = None
        self._max_token_per_minute: int | None = None
        self._max_token_per_request: int | None = None
        self._throttle_check_interval: float | None = None

    # --- Configuration Properties ---

    @property
    def max_request_per_minute(self) -> int:
        """Requests allowed per minute, from `LLM_MAX_REQUEST_PER_MINUTE` (default 60).

        `0` blocks every request — checked with `is not None` so an explicit
        zero isn't mistaken for "unset" and silently replaced by the default.
        """
        if self._max_request_per_minute is not None:
            return self._max_request_per_minute
        cfg_value = getattr(CFG, "LLM_MAX_REQUEST_PER_MINUTE", None)
        return cfg_value if cfg_value is not None else 60

    @max_request_per_minute.setter
    def max_request_per_minute(self, value: int):
        """Override the per-minute request cap for this limiter."""
        self._max_request_per_minute = value

    @property
    def max_token_per_minute(self) -> int:
        """Tokens allowed per minute, from `LLM_MAX_TOKEN_PER_MINUTE` (default 100k).

        `0` blocks every request — checked with `is not None` so an explicit
        zero isn't mistaken for "unset" and silently replaced by the default.
        """
        if self._max_token_per_minute is not None:
            return self._max_token_per_minute
        cfg_value = getattr(CFG, "LLM_MAX_TOKEN_PER_MINUTE", None)
        return cfg_value if cfg_value is not None else 100_000

    @max_token_per_minute.setter
    def max_token_per_minute(self, value: int):
        """Override the per-minute token cap for this limiter."""
        self._max_token_per_minute = value

    @property
    def max_token_per_request(self) -> int:
        """Tokens allowed in one request, from `LLM_MAX_TOKEN_PER_REQUEST` (default 16k).

        `fit_context_window` trims history to stay under this. `0` blocks
        every request — checked with `is not None` so an explicit zero isn't
        mistaken for "unset" and silently replaced by the default.
        """
        if self._max_token_per_request is not None:
            return self._max_token_per_request
        cfg_value = getattr(CFG, "LLM_MAX_TOKEN_PER_REQUEST", None)
        return cfg_value if cfg_value is not None else 16_000

    @max_token_per_request.setter
    def max_token_per_request(self, value: int):
        """Override the per-request token cap for this limiter."""
        self._max_token_per_request = value

    @property
    def throttle_check_interval(self) -> float:
        """Seconds slept between capacity re-checks while throttled (default 0.1)."""
        if self._throttle_check_interval is not None:
            return self._throttle_check_interval
        return getattr(CFG, "LLM_THROTTLE_SLEEP", None) or 0.1

    @throttle_check_interval.setter
    def throttle_check_interval(self, value: float):
        """Override the throttle poll interval for this limiter."""
        self._throttle_check_interval = value

    @property
    def use_tiktoken(self) -> bool:
        """Whether tokens are counted with tiktoken rather than estimated.

        Accurate but slower, and requires the `tiktoken` package. Off by
        default; enable with `ENABLE_TIKTOKEN`.
        """
        return CFG.ENABLE_TIKTOKEN

    @property
    def tiktoken_encoding(self) -> str:
        """Encoding name used when `use_tiktoken` is on (default `cl100k_base`)."""
        return getattr(CFG, "TIKTOKEN_ENCODING_NAME", "cl100k_base")

    # --- Public API ---

    def fit_context_window(
        self, history: list[Any], new_message: Any, reserved_tokens: int = 0
    ) -> list[Any]:
        """
        Prunes the history (removing oldest turns) so that 'history + new_message'
        fits within 'max_tokens_per_request'.
        Ensures strict tool call pairing by removing full conversation turns.

        reserved_tokens: tokens already consumed by system prompt, tool schemas, etc.
        """
        if not history:
            return history

        available = max(0, int(self.max_token_per_request * 0.90) - reserved_tokens)

        new_msg_tokens = self._count_tokens(new_message)
        if new_msg_tokens > available:
            return []

        n = len(history)

        # Precompute per-message costs in O(n) to avoid O(n²) re-counting in the
        # pruning loop.  Must replicate to_str's list-level semantics exactly:
        # bodies are counted per-message with skip_instructions=True, and only the
        # LAST instruction in the current window is counted once (historical
        # instructions are not replayed by pydantic-ai).  Counting each message
        # individually with skip_instructions=False would include every message's
        # instructions, wildly over-estimating the cost for long conversations.
        msg_body_tokens = [
            self._count_tokens(self.to_str(msg, skip_instructions=True))
            for msg in history
        ]
        msg_instr_tokens = []
        for msg in history:
            instr = getattr(msg, "instructions", None)
            msg_instr_tokens.append(
                self._count_tokens(self.to_str(instr, skip_instructions=True))
                if instr
                else 0
            )

        # last_instr_from[i] = index of the last message with instructions in
        # history[i:], or -1.  Allows O(1) "what is the active instruction cost
        # for the window starting at i?" lookups during the pruning loop.
        last_instr_from = [-1] * (n + 1)
        for i in range(n - 1, -1, -1):
            last_instr_from[i] = (
                i if msg_instr_tokens[i] > 0 else last_instr_from[i + 1]
            )

        def _instr_cost(from_idx: int) -> int:
            li = last_instr_from[from_idx]
            return msg_instr_tokens[li] if li >= 0 else 0

        total_tokens = sum(msg_body_tokens) + _instr_cost(0)

        if total_tokens + new_msg_tokens <= available:
            return list(history)

        start = 0
        while start < n:
            if total_tokens + new_msg_tokens <= available:
                break

            # Find the start of the next user turn after the current position.
            next_turn = -1
            for i in range(start + 1, n):
                if is_turn_start(history[i]):
                    next_turn = i
                    break

            if next_turn == -1:
                # No subsequent turn found; clear all remaining history.
                total_tokens = 0
                start = n
                break

            # Subtract body tokens for the dropped messages.
            for i in range(start, next_turn):
                total_tokens -= msg_body_tokens[i]

            # Adjust for the instruction-window shift: the "active last instruction"
            # may change as old messages are pruned from the front.
            total_tokens += _instr_cost(next_turn) - _instr_cost(start)

            start = next_turn

        return history[start:]

    async def acquire(self, content: Any, notifier: Callable[[str], Any] | None = None):
        """
        Acquires permission to proceed with the given content.
        Calculates token count internally and waits if rate limits are exceeded.
        """
        # Calculate tokens once
        estimated_tokens = self._count_tokens(content)

        # 1. Prune logs older than 60 seconds
        self.prune_logs()

        # 2. Check limits loop
        notified = False
        while not self.can_proceed(estimated_tokens):
            wait_time = self.calculate_wait_time(estimated_tokens)
            reason = self.get_limit_reason(estimated_tokens)

            if notifier:
                msg = f"Rate Limit reached: {reason}. Waiting {wait_time:.1f}s..."
                # Only notify once or if status changes? Simple is better.
                notifier(stylize_info(msg))
                notified = True

            await asyncio.sleep(self.throttle_check_interval)
            self.prune_logs()

        if notified and notifier:
            notifier("\n")  # Clear status

        # 3. Record usage
        now = time.time()
        self.request_log.append(now)
        self.token_log.append((now, estimated_tokens))

    def count_tokens(self, content: Any) -> int:
        """Public alias for internal counter."""
        return self._count_tokens(content)

    def truncate_text(self, text: str, max_tokens: int) -> str:
        """Truncates a string to a maximum number of tokens."""
        if self.use_tiktoken:
            try:
                # lazy: heavy third-party
                import tiktoken

                enc = tiktoken.get_encoding(self.tiktoken_encoding)
                tokens = enc.encode(text)
                if len(tokens) > max_tokens:
                    truncated_tokens = tokens[:max_tokens]
                    return enc.decode(truncated_tokens)
                return text
            except Exception as e:
                # Fallback if tiktoken fails for any reason (missing package,
                # unknown encoding name, corrupt/unfetchable BPE cache, …)
                CFG.LOGGER.debug(f"tiktoken truncate fallback: {e}")
        # Fallback approximation (char/4) for when tiktoken is not used or fails
        estimated_chars = max_tokens * 4
        if len(text) > estimated_chars:
            return text[:estimated_chars]
        return text

    # --- Helpers ---

    def _count_tokens(self, content: Any) -> int:
        text = self.to_str(content)
        if self.use_tiktoken:
            try:
                # lazy: heavy third-party
                import tiktoken

                enc = tiktoken.get_encoding(self.tiktoken_encoding)
                return len(enc.encode(text))
            except Exception as e:
                # Fallback to the char/4 approximation if tiktoken fails for
                # any reason (missing package, unknown encoding name, corrupt
                # or unfetchable BPE cache). Counting must never crash the
                # history pipeline — it runs before every model call.
                CFG.LOGGER.debug(f"tiktoken count fallback: {e}")
        # Fallback approximation (char/4)
        return len(text) // 4

    def to_str(self, content: Any, skip_instructions: bool = False) -> str:
        """Flatten arbitrary message content into a string for token counting."""
        if isinstance(content, str):
            return content
        if isinstance(content, (int, float, bool)) or content is None:
            return str(content)

        # Handle collections to avoid json.dumps/str() overhead on large objects
        if isinstance(content, list):
            res = "".join(self.to_str(item, skip_instructions=True) for item in content)
            # If counting a list of messages, only count the latest instructions.
            # This aligns with Pydantic AI's behavior where only the current instructions
            # are sent to the model, and historical instructions are not replayed.
            if not skip_instructions:
                for item in reversed(content):
                    if hasattr(item, "instructions"):
                        instr = getattr(item, "instructions", None)
                        if instr:
                            res += self.to_str(instr, skip_instructions=True)
                            break
            return res

        if isinstance(content, dict):
            # Join key-value pairs with spaces for better token counting
            items = []
            for k, v in content.items():
                key_str = self.to_str(k, skip_instructions=skip_instructions)
                val_str = self.to_str(v, skip_instructions=skip_instructions)
                items.append(f"{key_str}: {val_str}")
            return " ".join(items)

        res = ""
        # 1. Handle parts (ModelRequest, ModelResponse)
        if hasattr(content, "parts"):
            res += self.to_str(
                getattr(content, "parts", []), skip_instructions=skip_instructions
            )

        # 2. instructions field (ModelRequest)
        # Only count if not skipping (i.e. it's considered the "latest" context)
        if not skip_instructions and hasattr(content, "instructions"):
            instr = getattr(content, "instructions", None)
            if instr:
                res += self.to_str(instr, skip_instructions=True)

        # 3. content (UserPromptPart, TextPart, ToolReturnPart, SystemPromptPart, etc.)
        if hasattr(content, "content"):
            res += self.to_str(
                getattr(content, "content", None), skip_instructions=skip_instructions
            )

        # 4. args (ToolCallPart)
        if hasattr(content, "args"):
            res += self.to_str(
                getattr(content, "args", {}), skip_instructions=skip_instructions
            )

        if res:
            return res

        # Fallback for other objects
        try:
            return str(content)
        except Exception:
            return ""

    def prune_logs(self):
        """Drop request/token log entries older than the 60s rate window."""
        now = time.time()
        window_start = now - 60

        while self.request_log and self.request_log[0] < window_start:
            self.request_log.popleft()

        while self.token_log and self.token_log[0][0] < window_start:
            self.token_log.popleft()

    def can_proceed(self, tokens: int) -> bool:
        """Whether a request needing `tokens` fits under the current rate limits."""
        # A limit of 0 blocks everything: a request budget of 0 never admits
        # any request, and a token budget of 0 rejects any positive token ask.
        requests_ok = len(self.request_log) < self.max_request_per_minute

        current_tokens = sum(t for _, t in self.token_log)
        tokens_ok = (current_tokens + tokens) <= self.max_token_per_minute

        return requests_ok and tokens_ok

    def get_limit_reason(self, tokens: int) -> str:
        """Which limit (requests or tokens) is currently blocking progress."""
        if len(self.request_log) >= self.max_request_per_minute:
            return f"Max Requests ({self.max_request_per_minute}/min)"
        return f"Max Tokens ({self.max_token_per_minute}/min)"

    def calculate_wait_time(self, tokens: int) -> float:
        """Seconds to wait before a request needing `tokens` would be allowed."""
        now = time.time()
        wait = 1.0

        # If request limit hit, wait until oldest request expires. With a
        # request budget of 0 the log can be empty while still over-limit, so
        # only read the oldest entry when one exists.
        if len(self.request_log) >= self.max_request_per_minute:
            if self.request_log:
                oldest = self.request_log[0]
                wait = max(0.1, 60 - (now - oldest))

        # If token limit hit, wait until enough tokens expire
        current_tokens = sum(t for _, t in self.token_log)
        if current_tokens + tokens > self.max_token_per_minute:
            needed = (current_tokens + tokens) - self.max_token_per_minute
            freed = 0
            for ts, count in self.token_log:
                freed += count
                if freed >= needed:
                    wait = max(wait, 60 - (now - ts))
                    break

        return wait


llm_limiter = LLMLimiter()
