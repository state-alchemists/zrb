import asyncio
import time
from collections import deque
from typing import Callable

from zrb.config import CFG


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
        token_counter_fn: Callable[[str], int] | None = None,
    ):
        self._max_requests_per_minute = max_requests_per_minute
        self._max_tokens_per_minute = max_tokens_per_minute
        self._max_tokens_per_request = max_tokens_per_request
        self._throttle_sleep = throttle_sleep
        self._token_counter_fn = token_counter_fn
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
    def token_counter_fn(self) -> Callable[[str], int]:
        if self._token_counter_fn is not None:
            return self._token_counter_fn
        return lambda x: len(x.split())

    def set_max_requests_per_minute(self, value: int):
        self._max_requests_per_minute = value

    def set_max_tokens_per_minute(self, value: int):
        self._max_tokens_per_minute = value

    def set_max_tokens_per_request(self, value: int):
        self._max_tokens_per_request = value

    def set_throttle_sleep(self, value: float):
        self._throttle_sleep = value

    def set_token_counter_fn(self, fn: Callable[[str], int]):
        self._token_counter_fn = fn

    async def throttle(self, prompt: str):
        now = time.time()
        tokens = self.token_counter_fn(prompt)
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
