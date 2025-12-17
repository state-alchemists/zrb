import asyncio
import json
import time
from collections import deque
from typing import Any, Callable

from zrb.config.config import CFG


class LLMRateLimitter:
    """
    Helper class to enforce LLM API rate limits and throttling.
    Tracks requests and tokens in a rolling 60-second window.
    """

    def __init__(
        self,
        max_requests_per_minute: int | None = None,
        max_tokens_per_minute: int | None = None,
        max_tokens_per_request: int | None = None,
        max_tokens_per_tool_call_result: int | None = None,
        throttle_sleep: float | None = None,
        use_tiktoken: bool | None = None,
        tiktoken_encoding_name: str | None = None,
    ):
        self._max_requests_per_minute = max_requests_per_minute
        self._max_tokens_per_minute = max_tokens_per_minute
        self._max_tokens_per_request = max_tokens_per_request
        self._max_tokens_per_tool_call_result = max_tokens_per_tool_call_result
        self._throttle_sleep = throttle_sleep
        self._use_tiktoken = use_tiktoken
        self._tiktoken_encoding_name = tiktoken_encoding_name
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
    def max_tokens_per_tool_call_result(self) -> int:
        if self._max_tokens_per_tool_call_result is not None:
            return self._max_tokens_per_tool_call_result
        return CFG.LLM_MAX_TOKENS_PER_TOOL_CALL_RESULT

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

    def set_max_tokens_per_tool_call_result(self, value: int):
        self._max_tokens_per_tool_call_result = value

    def set_throttle_sleep(self, value: float):
        self._throttle_sleep = value

    def count_token(self, prompt: Any) -> int:
        str_prompt = self._prompt_to_str(prompt)
        if not self.use_tiktoken:
            return self._fallback_count_token(str_prompt)
        try:
            import tiktoken

            enc = tiktoken.get_encoding(self.tiktoken_encoding_name)
            return len(enc.encode(str_prompt))
        except Exception:
            return self._fallback_count_token(str_prompt)

    def _fallback_count_token(self, str_prompt: str) -> int:
        return len(str_prompt) // 4

    def clip_prompt(self, prompt: Any, limit: int) -> str:
        str_prompt = self._prompt_to_str(prompt)
        if not self.use_tiktoken:
            return self._fallback_clip_prompt(str_prompt, limit)
        try:
            import tiktoken

            enc = tiktoken.get_encoding(self.tiktoken_encoding_name)
            tokens = enc.encode(str_prompt)
            if len(tokens) <= limit:
                return str_prompt
            truncated = tokens[: limit - 3]
            clipped_text = enc.decode(truncated)
            return clipped_text + "..."
        except Exception:
            return self._fallback_clip_prompt(str_prompt, limit)

    def _fallback_clip_prompt(self, str_prompt: str, limit: int) -> str:
        char_limit = limit * 4 if limit * 4 <= 10 else limit * 4 - 10
        return str_prompt[:char_limit] + "..."

    async def throttle(
        self,
        prompt: Any,
        throttle_notif_callback: Callable[[str], Any] | None = None,
    ):
        now = time.time()
        str_prompt = self._prompt_to_str(prompt)
        tokens = self.count_token(str_prompt)
        # Clean up old entries
        while self.request_times and now - self.request_times[0] > 60:
            self.request_times.popleft()
        while self.token_times and now - self.token_times[0][0] > 60:
            self.token_times.popleft()
        # Check per-request token limit
        if tokens > self.max_tokens_per_request:
            raise ValueError(
                (
                    "Request exceeds max_tokens_per_request "
                    f"({tokens} > {self.max_tokens_per_request})."
                )
            )
        if tokens > self.max_tokens_per_minute:
            raise ValueError(
                (
                    "Request exceeds max_tokens_per_minute "
                    f"({tokens} > {self.max_tokens_per_minute})."
                )
            )
        # Wait if over per-minute request or token limit
        while (
            len(self.request_times) >= self.max_requests_per_minute
            or sum(t for _, t in self.token_times) + tokens > self.max_tokens_per_minute
        ):
            if throttle_notif_callback is not None:
                if len(self.request_times) >= self.max_requests_per_minute:
                    rpm = len(self.request_times)
                    throttle_notif_callback(
                        f"Max request per minute exceeded: {rpm} of {self.max_requests_per_minute}"
                    )
                else:
                    tpm = sum(t for _, t in self.token_times) + tokens
                    throttle_notif_callback(
                        f"Max token per minute exceeded: {tpm} of {self.max_tokens_per_minute}"
                    )
            await asyncio.sleep(self.throttle_sleep)
            now = time.time()
            while self.request_times and now - self.request_times[0] > 60:
                self.request_times.popleft()
            while self.token_times and now - self.token_times[0][0] > 60:
                self.token_times.popleft()
        # Record this request
        self.request_times.append(now)
        self.token_times.append((now, tokens))

    def _prompt_to_str(self, prompt: Any) -> str:
        try:
            return json.dumps(prompt)
        except Exception:
            return f"{prompt}"


llm_rate_limitter = LLMRateLimitter()
