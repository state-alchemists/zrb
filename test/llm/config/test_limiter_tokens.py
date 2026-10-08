import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from pydantic_ai.messages import ModelRequest, UserPromptPart

from zrb.llm.config.limiter import LLMLimiter, is_turn_start


def _fake_tiktoken(encode_len=None, decode_value="DECODED"):
    "Build a fake ``tiktoken`` module whose encoder is controllable."
    enc = MagicMock()
    if encode_len is not None:
        enc.encode.return_value = list(range(encode_len))
    enc.decode.return_value = decode_value
    module = MagicMock()
    module.get_encoding.return_value = enc
    return module, enc


@pytest.mark.asyncio
async def test_count_tokens_uses_tiktoken_when_enabled():
    "When tiktoken is enabled and importable, the encoder length is returned."
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
    "truncate_text decodes the truncated token slice when over the limit."
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

    enc.decode.assert_called_once()
    assert enc.decode.call_args.args[0] == list(range(5))


@pytest.mark.asyncio
async def test_truncate_text_uses_tiktoken_returns_unchanged_when_under_limit():
    "truncate_text returns the original text when token count is within the limit."
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
    "A tiktoken failure that is NOT ImportError (bad encoding name,"
    limiter = LLMLimiter()
    with (
        patch.object(
            LLMLimiter, "use_tiktoken", new_callable=PropertyMock, return_value=True
        ),
        patch("tiktoken.get_encoding", side_effect=ValueError("unknown encoding")),
    ):

        assert limiter.count_tokens("A" * 40) == 10


@pytest.mark.asyncio
async def test_truncate_text_falls_back_when_tiktoken_raises_non_import_error():
    "B1 companion: truncate_text already tolerated broad failures; confirm it"
    limiter = LLMLimiter()
    with (
        patch.object(
            LLMLimiter, "use_tiktoken", new_callable=PropertyMock, return_value=True
        ),
        patch("tiktoken.get_encoding", side_effect=ValueError("unknown encoding")),
    ):
        truncated = limiter.truncate_text("A" * 40, 5)
        assert truncated == "A" * 20


@pytest.mark.asyncio
async def test_llm_limiter_count_tokens():
    "Test count_tokens with string content."
    limiter = LLMLimiter()
    tokens = limiter.count_tokens("Hello world")
    assert tokens > 0


@pytest.mark.asyncio
async def test_llm_limiter_truncate_text():
    "Test truncate_text truncates long text."
    limiter = LLMLimiter()

    text = "A" * 30
    truncated = limiter.truncate_text(text, 5)

    assert len(truncated) <= 30


@pytest.mark.asyncio
async def test_llm_limiter_fit_context_window():
    "Test fit_context_window prunes when exceeding limit."
    limiter = LLMLimiter()

    limiter.max_token_per_request = 2

    msg1 = ModelRequest(parts=[UserPromptPart(content="Hello")])
    msg2 = ModelRequest(parts=[UserPromptPart(content="How are you?")])
    history = [msg1, msg2]

    new_msg = "I am fine"

    with patch("zrb.llm.config.limiter.is_turn_start", side_effect=[False, True]):
        pruned = limiter.fit_context_window(history, new_msg)
        assert len(pruned) < len(history)


@pytest.mark.asyncio
async def test_llm_limiter_acquire():
    "Test acquire proceeds immediately when under limits."
    limiter = LLMLimiter()
    limiter.max_request_per_minute = 100
    limiter.max_token_per_minute = 1000

    notifier = MagicMock()
    await limiter.acquire("Short message", notifier=notifier)
    assert not notifier.called


@pytest.mark.asyncio
async def test_llm_limiter_zero_request_limit_blocks_first_request():
    "A zero request budget blocks the first request."
    limiter = LLMLimiter()
    limiter.max_request_per_minute = 0
    limiter.max_token_per_minute = 1000
    limiter.throttle_check_interval = 0.01

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(limiter.acquire("hello"), timeout=0.1)


@pytest.mark.asyncio
async def test_llm_limiter_zero_token_limit_blocks_positive_tokens():
    "B10: a token budget of 0 must reject any request that needs tokens."
    limiter = LLMLimiter()
    limiter.max_request_per_minute = 100
    limiter.max_token_per_minute = 0
    limiter.throttle_check_interval = 0.01

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(limiter.acquire("hello world"), timeout=0.1)


def test_llm_limiter_properties():
    "Test limiter property getters and setters."
    limiter = LLMLimiter()

    limiter.max_request_per_minute = 50
    assert limiter.max_request_per_minute == 50

    limiter.max_token_per_minute = 5000
    assert limiter.max_token_per_minute == 5000

    limiter.max_token_per_request = 8000
    assert limiter.max_token_per_request == 8000

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
    "A trailing message appended after the anchored response (e.g. a fresh"
    limiter = LLMLimiter()
    limiter.max_token_per_request = 1_000
    history = [
        SimpleNamespace(usage=SimpleNamespace(input_tokens=800, output_tokens=0)),
        ModelRequest(parts=[UserPromptPart(content="y" * 500)]),
    ]

    result = limiter.fit_context_window(history, "next")

    assert result != history


def test_fit_context_window_prunes_incrementally_across_an_active_anchor():
    "Before the anchor is crossed, dropping an early turn must shrink the"
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

    assert result == history[1:]


def test_fit_context_window_subtracts_reserved_tokens_despite_an_anchor():
    "reserved_tokens reflects the *current* system prompt and can have"
    limiter = LLMLimiter()
    limiter.max_token_per_request = 1_000
    history = [
        ModelRequest(parts=[UserPromptPart(content="old turn")]),
        ModelRequest(parts=[UserPromptPart(content="recent turn")]),
        SimpleNamespace(usage=SimpleNamespace(input_tokens=800, output_tokens=0)),
    ]

    assert limiter.fit_context_window(history, "next", reserved_tokens=0) == history

    pruned = limiter.fit_context_window(history, "next", reserved_tokens=500)
    assert pruned != history


def test_llm_limiter_fit_context_window_empty():
    "Test fit_context_window with empty history."
    limiter = LLMLimiter()

    result = limiter.fit_context_window([], "new message")
    assert result == []


def test_llm_limiter_fit_context_window_no_prune_needed():
    "Test fit_context_window when no pruning is needed."
    limiter = LLMLimiter()
    limiter.max_token_per_request = 10000

    msg = ModelRequest(parts=[UserPromptPart(content="Hello")])
    history = [msg]

    result = limiter.fit_context_window(history, "new message")
    assert len(result) == 1


def test_is_turn_start_with_model_request():
    "Test is_turn_start with ModelRequest containing UserPromptPart."
    from pydantic_ai.messages import ModelRequest, UserPromptPart

    msg = ModelRequest(parts=[UserPromptPart(content="Hello")])
    assert is_turn_start(msg) is True


def test_is_turn_start_with_tool_return():
    "Test is_turn_start with ModelRequest containing ToolReturnPart."
    from pydantic_ai.messages import ModelRequest, ToolReturnPart, UserPromptPart

    msg = ModelRequest(
        parts=[
            UserPromptPart(content="Hello"),
            ToolReturnPart(tool_name="test", content="result", tool_call_id="1"),
        ]
    )
    assert is_turn_start(msg) is False


def test_is_turn_start_with_non_model_request():
    "Test is_turn_start with non-ModelRequest object."
    assert is_turn_start("not a model request") is False
    assert is_turn_start(None) is False
    assert is_turn_start(123) is False


def test_llm_limiter_count_tokens_with_list():
    "Test count_tokens with list content."
    limiter = LLMLimiter()

    result = limiter.count_tokens(["hello", "world"])
    assert result > 0


def test_llm_limiter_count_tokens_with_dict():
    "Test count_tokens with dict content."
    limiter = LLMLimiter()

    result = limiter.count_tokens({"key": "value"})
    assert result > 0


def test_llm_limiter_use_tiktoken_property():
    "Test use_tiktoken property."
    limiter = LLMLimiter()

    assert isinstance(limiter.use_tiktoken, bool)


def test_llm_limiter_tiktoken_encoding_property():
    "Test tiktoken_encoding property."
    limiter = LLMLimiter()
    assert isinstance(limiter.tiktoken_encoding, str)


@pytest.mark.asyncio
async def test_llm_limiter_acquire_behavior():
    "Test that acquire properly manages rate limiting behavior."
    import time

    limiter = LLMLimiter()
    limiter.max_request_per_minute = 100
    limiter.max_token_per_minute = 10000

    start = time.time()
    await limiter.acquire("test content")
    elapsed = time.time() - start

    assert elapsed < 1.0
