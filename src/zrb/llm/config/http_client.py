from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import httpx


@lru_cache(maxsize=1)
def _is_retry_supported() -> bool:
    try:
        from pydantic_ai.retries import AsyncTenacityTransport  # noqa: F401

        return True
    except ImportError:
        return False


def create_retrying_http_client(
    max_attempts: int, max_wait: float
) -> "httpx.AsyncClient | None":
    """Build an httpx AsyncClient that retries transient provider errors.

    Returns None when retries are disabled (max_attempts <= 1) or when the
    pydantic-ai retries module is unavailable; callers should fall through
    to the provider's default client in that case.
    """
    if max_attempts <= 1 or not _is_retry_supported():
        return None

    import httpx
    from httpx import HTTPStatusError
    from pydantic_ai.retries import (
        AsyncTenacityTransport,
        RetryConfig,
        wait_retry_after,
    )
    from tenacity import (
        retry_if_exception_type,
        stop_after_attempt,
        wait_exponential,
    )

    def _should_retry(response: "httpx.Response") -> None:
        # Retry on 429 (rate limit) and 5xx (transient server errors).
        if response.status_code == 429 or response.status_code >= 500:
            response.raise_for_status()

    transport = AsyncTenacityTransport(
        config=RetryConfig(
            retry=retry_if_exception_type(HTTPStatusError),
            wait=wait_retry_after(
                fallback_strategy=wait_exponential(multiplier=1, min=1, max=max_wait),
                max_wait=max_wait,
            ),
            stop=stop_after_attempt(max_attempts),
            reraise=True,
        ),
        validate_response=_should_retry,
    )
    return httpx.AsyncClient(transport=transport)
