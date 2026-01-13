import time
from unittest.mock import MagicMock, patch

import pytest

from zrb.config.llm_rate_limitter import LLMRateLimitter


@pytest.mark.asyncio
async def test_wait_time_calculation_tokens_logic():
    """
    Test that wait time is calculated correctly based on accumulative token expiry.
    Scenario:
    Limit: 5 tokens/min.
    T=0: 1 token
    T=1: 2 tokens
    T=2: 2 tokens
    Sum = 5.

    New request: 2 tokens.
    Needed to free: 5 + 2 - 5 = 2.

    1st item (T=0, 1 token) -> Frees 1. Not enough.
    2nd item (T=1, 2 tokens) -> Frees 1+2=3. Enough.

    Wait should be based on T=1. Expiry T=61.
    Current T=3.
    Wait = 61 - 3 = 58s.
    """
    limiter = LLMRateLimitter(
        max_requests_per_minute=10, max_tokens_per_minute=5, throttle_sleep=0.001
    )

    # Setup state
    base_time = 1000.0
    limiter.token_times.append((base_time + 0, 1))
    limiter.token_times.append((base_time + 1, 2))
    limiter.token_times.append((base_time + 2, 2))

    current_time = base_time + 3.0

    # We want to catch the callback message
    captured_messages = []

    def callback(msg, *args, **kwargs):
        captured_messages.append(msg)

    # We will mock time.time to return current_time initially, then increment to break loop?
    # No, we just want to verify the message generated in the first iteration.
    # We can throw an exception in asyncio.sleep to break the loop early
    # OR we can just check the logic by mocking time.time and ensure loop runs once.

    async def mock_sleep(duration):
        raise InterruptedError("Break Loop")

    with patch("time.time", return_value=current_time), patch(
        "asyncio.sleep", side_effect=mock_sleep
    ):

        try:
            # "dummy" prompt length 2 tokens (we will mock count_token)
            with patch.object(limiter, "count_token", return_value=2):
                await limiter.throttle("dummy", callback)
        except InterruptedError:
            pass

    assert len(captured_messages) > 0
    msg = captured_messages[0]

    # Calculation:
    # Needed 2.
    # Item 0 (1) -> Freed 1.
    # Item 1 (2) -> Freed 3. >= 2. Stop.
    # Item 1 time is base_time + 1.
    # Wait time = (base_time + 1) + 60 - current_time
    # Wait time = (1000 + 1) + 60 - (1000 + 3) = 1061 - 1003 = 58.

    assert "Waiting for 58.00 seconds" in msg


@pytest.mark.asyncio
async def test_wait_time_calculation_requests_logic():
    """
    Test request limit wait time.
    Limit: 2 requests/min.
    T=0: Req 1
    T=10: Req 2

    Current T=20.
    New Request.
    Wait for T=0 to expire. Expiry T=60.
    Wait = 60 - 20 = 40s.
    """
    limiter = LLMRateLimitter(
        max_requests_per_minute=2, max_tokens_per_minute=1000, throttle_sleep=0.001
    )

    base_time = 1000.0
    limiter.request_times.append(base_time + 0)
    limiter.request_times.append(base_time + 10)

    current_time = base_time + 20.0

    captured_messages = []

    def callback(msg, *args, **kwargs):
        captured_messages.append(msg)

    async def mock_sleep(duration):
        raise InterruptedError("Break Loop")

    with patch("time.time", return_value=current_time), patch(
        "asyncio.sleep", side_effect=mock_sleep
    ):

        try:
            with patch.object(limiter, "count_token", return_value=1):
                await limiter.throttle("dummy", callback)
        except InterruptedError:
            pass

    assert len(captured_messages) > 0
    msg = captured_messages[0]

    # Wait time = (base_time + 0) + 60 - (base_time + 20) = 40.
    assert "Waiting for 40.00 seconds" in msg
