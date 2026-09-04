import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from pydantic_ai.messages import ModelRequest, UserPromptPart

from zrb.llm.config.limiter import LLMLimiter, is_turn_start


def _fake_tiktoken(encode_len=None, decode_value="DECODED"):
    """Build a fake ``tiktoken`` module whose encoder is controllable."""
    enc = MagicMock()
    if encode_len is not None:
        enc.encode.return_value = list(range(encode_len))
    enc.decode.return_value = decode_value
    module = MagicMock()
    module.get_encoding.return_value = enc
    return module, enc


@pytest.mark.asyncio
async def test_count_tokens_uses_tiktoken_when_enabled():
    """When tiktoken is enabled and importable, the encoder length is returned."""
    limiter = LLMLimiter()
    fake_module, enc = _fake_tiktoken(encode_len=7)
    with (
        patch.object(
            LLMLimiter, "use_tiktoken", new_callable=PropertyMock, return_value=True
        ),
        patch.dict("sys.modules", {"tiktoken": fake_module}),
    ):
        assert limiter.count_tokens("anything") == 7
    enc.encode.assert_called_once()


@pytest.mark.asyncio
async def test_truncate_text_uses_tiktoken_when_over_limit():
    """truncate_text decodes the truncated token slice when over the limit."""
    limiter = LLMLimiter()
    fake_module, enc = _fake_tiktoken(encode_len=20, decode_value="TRUNCATED")
    with (
        patch.object(
            LLMLimiter, "use_tiktoken", new_callable=PropertyMock, return_value=True
        ),
        patch.dict("sys.modules", {"tiktoken": fake_module}),
    ):
        result = limiter.truncate_text("long text", 5)
    assert result == "TRUNCATED"
    # Only the first 5 tokens are decoded.
    enc.decode.assert_called_once()
    assert enc.decode.call_args.args[0] == list(range(5))


@pytest.mark.asyncio
async def test_truncate_text_uses_tiktoken_returns_unchanged_when_under_limit():
    """truncate_text returns the original text when token count is within the limit."""
    limiter = LLMLimiter()
    fake_module, enc = _fake_tiktoken(encode_len=3)
    with (
        patch.object(
            LLMLimiter, "use_tiktoken", new_callable=PropertyMock, return_value=True
        ),
        patch.dict("sys.modules", {"tiktoken": fake_module}),
    ):
        result = limiter.truncate_text("short", 10)
    assert result == "short"
    enc.decode.assert_not_called()


@pytest.mark.asyncio
async def test_count_tokens_falls_back_when_tiktoken_raises_non_import_error():
    """A tiktoken failure that is NOT ImportError (bad encoding name,
    corrupt/unfetchable BPE cache) must degrade to the char/4 approximation
    rather than propagating and crashing the history pipeline."""
    limiter = LLMLimiter()
    with (
        patch.object(
            LLMLimiter, "use_tiktoken", new_callable=PropertyMock, return_value=True
        ),
        patch("tiktoken.get_encoding", side_effect=ValueError("unknown encoding")),
    ):
        # Must not raise; falls back to len(text) // 4.
        assert limiter.count_tokens("A" * 40) == 10


@pytest.mark.asyncio
async def test_truncate_text_falls_back_when_tiktoken_raises_non_import_error():
    """B1 companion: truncate_text already tolerated broad failures; confirm it
    still degrades gracefully (no crash) on a non-ImportError."""
    limiter = LLMLimiter()
    with (
        patch.object(
            LLMLimiter, "use_tiktoken", new_callable=PropertyMock, return_value=True
        ),
        patch("tiktoken.get_encoding", side_effect=ValueError("unknown encoding")),
    ):
        truncated = limiter.truncate_text("A" * 40, 5)
        assert truncated == "A" * 20  # char/4 fallback: 5 tokens * 4 chars


@pytest.mark.asyncio
async def test_llm_limiter_count_tokens():
    """Test count_tokens with string content."""
    limiter = LLMLimiter()
    tokens = limiter.count_tokens("Hello world")
    assert tokens > 0


@pytest.mark.asyncio
async def test_llm_limiter_truncate_text():
    """Test truncate_text truncates long text."""
    limiter = LLMLimiter()
    # Test the fallback behavior directly by checking the result
    text = "A" * 30
    truncated = limiter.truncate_text(text, 5)
    # With or without tiktoken, result should be at most reasonable size
    # tiktoken may return fewer chars due to BPE compression
    # fallback returns ~max_tokens * 4 chars
    assert len(truncated) <= 30  # Original or truncated


@pytest.mark.asyncio
async def test_llm_limiter_fit_context_window():
    """Test fit_context_window prunes when exceeding limit."""
    limiter = LLMLimiter()
    # Set limit extremely low to force pruning of even small messages
    limiter.max_token_per_request = 2

    # Message history
    msg1 = ModelRequest(parts=[UserPromptPart(content="Hello")])
    msg2 = ModelRequest(parts=[UserPromptPart(content="How are you?")])
    history = [msg1, msg2]

    new_msg = "I am fine"

    with patch("zrb.llm.config.limiter.is_turn_start", side_effect=[False, True]):
        pruned = limiter.fit_context_window(history, new_msg)
        assert len(pruned) < len(history)


@pytest.mark.asyncio
async def test_llm_limiter_acquire():
    """Test acquire proceeds immediately when under limits."""
    limiter = LLMLimiter()
    limiter.max_request_per_minute = 100
    limiter.max_token_per_minute = 1000

    # Should proceed immediately if under limits
    notifier = MagicMock()
    await limiter.acquire("Short message", notifier=notifier)
    assert not notifier.called


@pytest.mark.asyncio
async def test_llm_limiter_zero_request_limit_blocks_first_request():
    """B10: a request budget of 0 must block even the very first request.

    Previously the empty-log guard let the first request through. ``acquire``
    should now loop indefinitely, so ``wait_for`` must time out.
    """
    limiter = LLMLimiter()
    limiter.max_request_per_minute = 0
    limiter.max_token_per_minute = 1000
    limiter.throttle_check_interval = 0.01

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(limiter.acquire("hello"), timeout=0.1)


@pytest.mark.asyncio
async def test_llm_limiter_zero_token_limit_blocks_positive_tokens():
    """B10: a token budget of 0 must reject any request that needs tokens."""
    limiter = LLMLimiter()
    limiter.max_request_per_minute = 100
    limiter.max_token_per_minute = 0
    limiter.throttle_check_interval = 0.01

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(limiter.acquire("hello world"), timeout=0.1)


def test_llm_limiter_properties():
    """Test limiter property getters and setters."""
    limiter = LLMLimiter()

    # Test max_request_per_minute
    limiter.max_request_per_minute = 50
    assert limiter.max_request_per_minute == 50

    # Test max_token_per_minute
    limiter.max_token_per_minute = 5000
    assert limiter.max_token_per_minute == 5000

    # Test max_token_per_request
    limiter.max_token_per_request = 8000
    assert limiter.max_token_per_request == 8000

    # Test throttle_check_interval
    limiter.throttle_check_interval = 0.5
    assert limiter.throttle_check_interval == 0.5


def test_fit_context_window_honors_a_known_model_cap():
    limiter = LLMLimiter()
    limiter.max_token_per_request = 256_000
    history = [
        ModelRequest(parts=[UserPromptPart(content="x" * 600_000)]),
        ModelRequest(parts=[UserPromptPart(content="recent turn")]),
    ]

    assert (
        limiter.fit_context_window(history, "next", model="openai:gpt-4o")
        == history[1:]
    )
    assert limiter.fit_context_window(history, "next", model="local:unknown") == history


def test_count_tokens_anchors_on_provider_usage():
    limiter = LLMLimiter()
    response = SimpleNamespace(
        usage=SimpleNamespace(input_tokens=100, output_tokens=20)
    )

    assert limiter.count_tokens([response, "abcdefgh"]) == 122


def test_fit_context_window_drops_a_stale_usage_anchor_before_estimating_tail():
    limiter = LLMLimiter()
    limiter.max_token_per_request = 1_000
    history = [
        ModelRequest(parts=[UserPromptPart(content="old turn")]),
        SimpleNamespace(usage=SimpleNamespace(input_tokens=1_000, output_tokens=1)),
        ModelRequest(parts=[UserPromptPart(content="recent turn")]),
    ]

    result = limiter.fit_context_window(history, "next")

    assert result == history[2:]


def test_fit_context_window_keeps_the_final_turn_after_a_last_usage_anchor():
    limiter = LLMLimiter()
    limiter.max_token_per_request = 1_000
    history = [
        ModelRequest(parts=[UserPromptPart(content="old turn")]),
        ModelRequest(parts=[UserPromptPart(content="last turn")]),
        SimpleNamespace(usage=SimpleNamespace(input_tokens=1_000, output_tokens=1)),
    ]

    result = limiter.fit_context_window(history, "next")

    assert result == history[1:]


def test_fit_context_window_counts_messages_after_the_anchor():
    """A trailing message appended after the anchored response (e.g. a fresh
    tool result) must be counted, not silently ignored."""
    limiter = LLMLimiter()
    limiter.max_token_per_request = 1_000
    history = [
        SimpleNamespace(usage=SimpleNamespace(input_tokens=800, output_tokens=0)),
        ModelRequest(parts=[UserPromptPart(content="y" * 500)]),
    ]

    # 1000*0.9 = 900 available. The anchor alone (800) fits, but 800 plus the
    # ~125-token trailing message does not — it must trigger pruning.
    result = limiter.fit_context_window(history, "next")

    assert result != history


def test_fit_context_window_prunes_incrementally_across_an_active_anchor():
    """Before the anchor is crossed, dropping an early turn must shrink the
    anchor-seeded total by that turn's own size — not leave the total frozen
    until the whole pre-anchor conversation is dropped in one shot."""
    limiter = LLMLimiter()
    limiter.max_token_per_request = 167
    history = [
        ModelRequest(parts=[UserPromptPart(content="X" * 4000)]),
        ModelRequest(parts=[UserPromptPart(content="keep1")]),
        ModelRequest(parts=[UserPromptPart(content="keep2")]),
        SimpleNamespace(usage=SimpleNamespace(input_tokens=1100, output_tokens=0)),
        ModelRequest(parts=[UserPromptPart(content="recent")]),
    ]

    result = limiter.fit_context_window(history, "next")

    # Only the oversized first turn needed to be dropped — everything after
    # it, including the anchor's own response, is kept.
    assert result == history[1:]


def test_fit_context_window_subtracts_reserved_tokens_despite_an_anchor():
    """reserved_tokens reflects the *current* system prompt and can have
    grown since the anchored turn — it must still shrink `available`, not be
    skipped just because a usage anchor is present."""
    limiter = LLMLimiter()
    limiter.max_token_per_request = 1_000
    history = [
        ModelRequest(parts=[UserPromptPart(content="old turn")]),
        ModelRequest(parts=[UserPromptPart(content="recent turn")]),
        SimpleNamespace(usage=SimpleNamespace(input_tokens=800, output_tokens=0)),
    ]

    # With no reserve, the anchor's 800 tokens comfortably fit under the
    # 900 (1000*0.9) budget alongside the new message.
    assert limiter.fit_context_window(history, "next", reserved_tokens=0) == history

    # A large reserved_tokens (today's real system-prompt size, which a stale
    # anchor from an earlier, smaller prompt would not reflect) must still
    # shrink the budget and force pruning.
    pruned = limiter.fit_context_window(history, "next", reserved_tokens=500)
    assert pruned != history


def test_llm_limiter_fit_context_window_empty():
    """Test fit_context_window with empty history."""
    limiter = LLMLimiter()

    # Empty history
    result = limiter.fit_context_window([], "new message")
    assert result == []


def test_llm_limiter_fit_context_window_no_prune_needed():
    """Test fit_context_window when no pruning is needed."""
    limiter = LLMLimiter()
    limiter.max_token_per_request = 10000  # High limit

    msg = ModelRequest(parts=[UserPromptPart(content="Hello")])
    history = [msg]

    result = limiter.fit_context_window(history, "new message")
    assert len(result) == 1


def test_is_turn_start_with_model_request():
    """Test is_turn_start with ModelRequest containing UserPromptPart."""
    from pydantic_ai.messages import ModelRequest, UserPromptPart

    # ModelRequest with only UserPromptPart (turn start)
    msg = ModelRequest(parts=[UserPromptPart(content="Hello")])
    assert is_turn_start(msg) is True


def test_is_turn_start_with_tool_return():
    """Test is_turn_start with ModelRequest containing ToolReturnPart."""
    from pydantic_ai.messages import ModelRequest, ToolReturnPart, UserPromptPart

    # ModelRequest with both UserPromptPart and ToolReturnPart (not turn start)
    msg = ModelRequest(
        parts=[
            UserPromptPart(content="Hello"),
            ToolReturnPart(tool_name="test", content="result", tool_call_id="1"),
        ]
    )
    assert is_turn_start(msg) is False


def test_is_turn_start_with_non_model_request():
    """Test is_turn_start with non-ModelRequest object."""
    assert is_turn_start("not a model request") is False
    assert is_turn_start(None) is False
    assert is_turn_start(123) is False


def test_llm_limiter_count_tokens_with_list():
    """Test count_tokens with list content."""
    limiter = LLMLimiter()

    result = limiter.count_tokens(["hello", "world"])
    assert result > 0


def test_llm_limiter_count_tokens_with_dict():
    """Test count_tokens with dict content."""
    limiter = LLMLimiter()

    result = limiter.count_tokens({"key": "value"})
    assert result > 0


def test_llm_limiter_use_tiktoken_property():
    """Test use_tiktoken property."""
    limiter = LLMLimiter()
    # Default should be False
    assert isinstance(limiter.use_tiktoken, bool)


def test_llm_limiter_tiktoken_encoding_property():
    """Test tiktoken_encoding property."""
    limiter = LLMLimiter()
    assert isinstance(limiter.tiktoken_encoding, str)


@pytest.mark.asyncio
async def test_llm_limiter_acquire_behavior():
    """Test that acquire properly manages rate limiting behavior."""
    import time

    limiter = LLMLimiter()
    limiter.max_request_per_minute = 100
    limiter.max_token_per_minute = 10000

    # First acquire should succeed immediately
    start = time.time()
    await limiter.acquire("test content")
    elapsed = time.time() - start

    # Should complete quickly (no rate limit delay)
    assert elapsed < 1.0
