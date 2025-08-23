import asyncio
import time
from collections import deque
from typing import Callable

from zrb.config.config import CFG


class LLMRateLimiter:
    """
    Helper class to enforce LLM API rate limits and throttling.
    Tracks requests and tokens in a rolling 60-second window.
    """

    def __init__(
        self,
        max_requests_per_minute: int | None = None,
        max_tokens_per_minute: int | None = None,
        max_tokens_per_request: int | None = None,
        throttle_sleep: float | None = None,
        use_tiktoken: bool | None = None,
        tiktoken_encodeing_name: str | None = None,
    ):
        self._max_requests_per_minute = max_requests_per_minute
        self._max_tokens_per_minute = max_tokens_per_minute
        self._max_tokens_per_request = max_tokens_per_request
        self._throttle_sleep = throttle_sleep
        self._use_tiktoken = use_tiktoken
        self._tiktoken_encoding_name = tiktoken_encodeing_name
        self.request_times = deque()
        self.token_times = deque()

    @property
    def max_requests_per_minute(self) -> int:
        if self._max_requests_per_minute is not None:
            return self._max_requests_per_minute
        return CFG.LLM_MAX_REQUESTS_PER_MINUTE

    @property
    def max_tokens_per_minute(self) -> int:
        if self._max_tokens_per_minute is not None:
            return self._max_tokens_per_minute
        return CFG.LLM_MAX_TOKENS_PER_MINUTE

    @property
    def max_tokens_per_request(self) -> int:
        if self._max_tokens_per_request is not None:
            return self._max_tokens_per_request
        return CFG.LLM_MAX_TOKENS_PER_REQUEST

    @property
    def throttle_sleep(self) -> float:
        if self._throttle_sleep is not None:
            return self._throttle_sleep
        return CFG.LLM_THROTTLE_SLEEP

    @property
    def use_tiktoken(self) -> bool:
        if self._use_tiktoken is not None:
            return self._use_tiktoken
        return CFG.USE_TIKTOKEN

    @property
    def tiktoken_encoding_name(self) -> str:
        if self._tiktoken_encoding_name is not None:
            return self._tiktoken_encoding_name
        return CFG.TIKTOKEN_ENCODING_NAME

    def set_max_requests_per_minute(self, value: int):
        self._max_requests_per_minute = value

    def set_max_tokens_per_minute(self, value: int):
        self._max_tokens_per_minute = value

    def set_max_tokens_per_request(self, value: int):
        self._max_tokens_per_request = value

    def set_throttle_sleep(self, value: float):
        self._throttle_sleep = value

    def count_token(self, prompt: str) -> int:
        if not self.use_tiktoken:
            return self._fallback_count_token(prompt)
        try:
            import tiktoken

            enc = tiktoken.get_encoding(self.tiktoken_encoding_name)
            return len(enc.encode(prompt))
        except Exception:
            return self._fallback_count_token(prompt)

    def _fallback_count_token(self, prompt: str) -> int:
        return len(prompt) // 4

    def clip_prompt(self, prompt: str, limit: int) -> str:
        if not self.use_tiktoken:
            return self._fallback_clip_prompt(prompt, limit)
        try:
            import tiktoken

            enc = tiktoken.get_encoding("cl100k_base")
            tokens = enc.encode(prompt)
            if len(tokens) <= limit:
                return prompt
            truncated = tokens[: limit - 3]
            clipped_text = enc.decode(truncated)
            return clipped_text + "..."
        except Exception:
            return self._fallback_clip_prompt(prompt, limit)

    def _fallback_clip_prompt(self, prompt: str, limit: int) -> str:
        char_limit = limit * 4 if limit * 4 <= 10 else limit * 4 - 10
        return prompt[:char_limit] + "..."

    async def throttle(
        self, prompt: str, throttle_notif_callback: Callable | None = None
    ):
        now = time.time()
        tokens = self.count_token(prompt)
        # Clean up old entries
        while self.request_times and now - self.request_times[0] > 60:
            self.request_times.popleft()
        while self.token_times and now - self.token_times[0][0] > 60:
            self.token_times.popleft()
        # Check per-request token limit
        if tokens > self.max_tokens_per_request:
            raise ValueError(
                f"Request exceeds max_tokens_per_request ({self.max_tokens_per_request})."
            )
        # Wait if over per-minute request or token limit
        while (
            len(self.request_times) >= self.max_requests_per_minute
            or sum(t for _, t in self.token_times) + tokens > self.max_tokens_per_minute
        ):
            if throttle_notif_callback is not None:
                throttle_notif_callback()
            await asyncio.sleep(self.throttle_sleep)
            now = time.time()
            while self.request_times and now - self.request_times[0] > 60:
                self.request_times.popleft()
            while self.token_times and now - self.token_times[0][0] > 60:
                self.token_times.popleft()
        # Record this request
        self.request_times.append(now)
        self.token_times.append((now, tokens))


llm_rate_limitter = LLMRateLimiter()
