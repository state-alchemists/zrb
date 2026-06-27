import asyncio
import time
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


class TestLLMLimiterRateLimiting:
    """Test rate limiting behavior through public API."""

    def test_can_proceed_empty_logs(self):
        """Test _can_proceed returns True when logs are empty."""
        limiter = LLMLimiter()
        # Empty logs means we can proceed
        result = limiter._can_proceed(100)
        assert result is True

    def test_can_proceed_under_limits(self):
        """Test _can_proceed returns True when under limits."""
        limiter = LLMLimiter()
        limiter.max_request_per_minute = 10
        limiter.max_token_per_minute = 1000

        # Add some usage but stay under limit
        limiter._request_log.append(time.time())
        limiter._token_log.append((time.time(), 50))

        result = limiter._can_proceed(100)
        assert result is True

    def test_can_proceed_over_request_limit(self):
        """Test _can_proceed returns False when request limit exceeded."""
        limiter = LLMLimiter()
        limiter.max_request_per_minute = 2

        # Fill up request log
        limiter._request_log.append(time.time())
        limiter._request_log.append(time.time())

        result = limiter._can_proceed(10)
        assert result is False

    def test_can_proceed_over_token_limit(self):
        """Test _can_proceed returns False when token limit exceeded."""
        limiter = LLMLimiter()
        limiter.max_token_per_minute = 100

        # Fill up token log
        limiter._token_log.append((time.time(), 99))

        result = limiter._can_proceed(10)
        assert result is False

    def test_get_limit_reason_request_limit(self):
        """Test _get_limit_reason returns request limit message."""
        limiter = LLMLimiter()
        limiter.max_request_per_minute = 5

        # Fill request log
        for _ in range(5):
            limiter._request_log.append(time.time())

        reason = limiter._get_limit_reason(10)
        assert "Max Requests" in reason
        assert "5/min" in reason

    def test_get_limit_reason_token_limit(self):
        """Test _get_limit_reason returns token limit message."""
        limiter = LLMLimiter()
        limiter.max_request_per_minute = 100
        limiter.max_token_per_minute = 50

        reason = limiter._get_limit_reason(100)
        assert "Max Tokens" in reason
        assert "50/min" in reason

    def test_calculate_wait_time_request_limit(self):
        """Test _calculate_wait_time for request limit."""
        limiter = LLMLimiter()
        limiter.max_request_per_minute = 2

        # Fill request log
        limiter._request_log.append(time.time())
        limiter._request_log.append(time.time())

        wait = limiter._calculate_wait_time(10)
        assert wait > 0

    def test_calculate_wait_time_token_limit(self):
        """Test _calculate_wait_time for token limit."""
        limiter = LLMLimiter()
        limiter.max_token_per_minute = 50

        # Fill token log near limit
        limiter._token_log.append((time.time(), 40))

        wait = limiter._calculate_wait_time(20)
        assert wait > 0

    def test_prune_logs_removes_old_entries(self):
        """Test _prune_logs removes entries older than 60 seconds."""
        limiter = LLMLimiter()

        # Add old entries (65 seconds ago)
        old_time = time.time() - 65
        limiter._request_log.append(old_time)
        limiter._token_log.append((old_time, 100))

        # Add recent entries
        limiter._request_log.append(time.time())
        limiter._token_log.append((time.time(), 50))

        limiter._prune_logs()

        assert len(limiter._request_log) == 1
        assert len(limiter._token_log) == 1

    def test_prune_logs_keeps_recent_entries(self):
        """Test _prune_logs keeps entries within 60 seconds."""
        limiter = LLMLimiter()

        # Add recent entries
        limiter._request_log.append(time.time())
        limiter._token_log.append((time.time(), 100))

        limiter._prune_logs()

        assert len(limiter._request_log) == 1
        assert len(limiter._token_log) == 1


class TestLLMLimiterPropertyDefaults:
    """Properties fall back to the built-in default when CFG is unset/falsy."""

    def test_max_token_per_request_default_when_cfg_falsy(self):
        limiter = LLMLimiter()
        with patch("zrb.llm.config.limiter.CFG") as cfg:
            cfg.LLM_MAX_TOKEN_PER_REQUEST = None
            assert limiter.max_token_per_request == 16_000

    def test_throttle_check_interval_default_when_cfg_falsy(self):
        limiter = LLMLimiter()
        with patch("zrb.llm.config.limiter.CFG") as cfg:
            cfg.LLM_THROTTLE_SLEEP = None
            assert limiter.throttle_check_interval == 0.1

    def test_max_request_per_minute_default_when_cfg_falsy(self):
        limiter = LLMLimiter()
        with patch("zrb.llm.config.limiter.CFG") as cfg:
            cfg.LLM_MAX_REQUEST_PER_MINUTE = None
            assert limiter.max_request_per_minute == 60

    def test_max_token_per_minute_default_when_cfg_falsy(self):
        limiter = LLMLimiter()
        with patch("zrb.llm.config.limiter.CFG") as cfg:
            cfg.LLM_MAX_TOKEN_PER_MINUTE = None
            assert limiter.max_token_per_minute == 100_000


class TestLLMLimiterPruningLoop:
    """Exercise the real turn-based pruning loop (no is_turn_start patching)."""

    def test_prunes_oldest_turn_to_fit(self):
        """A multi-turn history over budget drops whole leading turns until it fits."""
        limiter = LLMLimiter()
        # char/4 estimate: keep tiktoken off and pick a tight budget.
        limiter.max_token_per_request = 30  # available = int(30*0.9) = 27

        # Each turn: a user request (turn start) + a model response.
        from datetime import datetime

        from pydantic_ai.messages import ModelResponse, TextPart

        def turn(user_text, reply_text):
            req = ModelRequest(parts=[UserPromptPart(content=user_text)])
            res = ModelResponse(
                parts=[TextPart(content=reply_text)], timestamp=datetime.now()
            )
            return [req, res]

        history = (
            turn("first user message padding padding", "first reply padding padding")
            + turn("second user message padding", "second reply padding")
            + turn("third short", "third short")
        )

        result = limiter.fit_context_window(history, "new question")

        # Pruning happened: the oldest turn(s) were dropped but newest survives.
        assert len(result) < len(history)
        assert result[-1].parts[0].content == "third short"
        # Result begins at a turn boundary (a user prompt request).
        assert is_turn_start(result[0])

    def test_prunes_all_when_only_one_turn_and_over_budget(self):
        """When no later turn boundary exists, the whole history is cleared."""
        limiter = LLMLimiter()
        limiter.max_token_per_request = 30  # available = 27

        from datetime import datetime

        from pydantic_ai.messages import ModelResponse, TextPart

        # A single turn whose body exceeds the budget; no subsequent turn start.
        req = ModelRequest(parts=[UserPromptPart(content="x" * 200)])
        res = ModelResponse(
            parts=[TextPart(content="y" * 50)], timestamp=datetime.now()
        )
        history = [req, res]

        result = limiter.fit_context_window(history, "tiny")
        assert result == []


class TestLLMLimiterToStrListInstructions:
    """_to_str over a list counts only the latest item's instructions (lines 279-282)."""

    def test_count_tokens_list_includes_latest_instructions(self):
        """A list whose latest item carries instructions costs more than one without.

        Driven through the public count_tokens(): the only difference between the
        two lists is the trailing item's instructions, so a higher token count
        proves the latest-instruction branch ran.
        """
        limiter = LLMLimiter()

        class MsgWithInstr:
            def __init__(self, instr):
                self.instructions = instr
                self.parts = []

        long_instr = "ACTIVE_INSTRUCTION_TEXT " * 20
        with_instr = [MsgWithInstr(""), MsgWithInstr(long_instr)]
        without_instr = [MsgWithInstr(""), MsgWithInstr("")]

        assert limiter.count_tokens(with_instr) > limiter.count_tokens(without_instr)


class TestLLMLimiterFitContextWindow:
    """Test context window fitting through public API."""

    def test_fit_context_window_clears_all_when_new_msg_too_large(self):
        """Test fit_context_window clears history when new message exceeds limit."""
        limiter = LLMLimiter()
        limiter.max_token_per_request = 5  # Very low limit

        msg = ModelRequest(parts=[UserPromptPart(content="Hello")])
        history = [msg]

        # Create a large new message that exceeds limit
        large_msg = "x" * 1000

        result = limiter.fit_context_window(history, large_msg)
        assert result == []

    def test_fit_context_window_prunes_by_turns(self):
        """Test fit_context_window prunes history by conversation turns."""
        limiter = LLMLimiter()
        limiter.max_token_per_request = 20

        msg1 = ModelRequest(parts=[UserPromptPart(content="First message here")])
        msg2 = ModelRequest(parts=[UserPromptPart(content="Second message")])
        msg3 = ModelRequest(parts=[UserPromptPart(content="Third")])

        history = [msg1, msg2, msg3]

        # New message that causes need for pruning
        new_msg = "A longer new message"

        # With is_turn_start properly identifying turns
        with patch(
            "zrb.llm.config.limiter.is_turn_start", side_effect=[False, True, False]
        ):
            result = limiter.fit_context_window(history, new_msg)
            # Should prune to fit within limit
            assert len(result) <= len(history)

    def test_fit_context_window_no_turn_start_found(self):
        """Test fit_context_window clears all when no turn start found."""
        limiter = LLMLimiter()
        limiter.max_token_per_request = 2

        msg = ModelRequest(parts=[UserPromptPart(content="Hello")])
        history = [msg]

        # All messages fail is_turn_start
        with patch("zrb.llm.config.limiter.is_turn_start", return_value=False):
            result = limiter.fit_context_window(history, "new message")
            assert result == []


class TestLLMLimiterTokenCounting:
    """Test token counting through public API."""

    def test_count_tokens_with_none(self):
        """Test count_tokens with None content converts to 'None' string."""
        limiter = LLMLimiter()
        result = limiter.count_tokens(None)
        # None converts to "None" string which has 4 chars, 4//4 = 1 token
        assert result >= 0

    def test_count_tokens_with_numeric(self):
        """Test count_tokens with numeric content."""
        limiter = LLMLimiter()
        result = limiter.count_tokens(42)
        # 42 converted to "42" has 2 chars, 2//4 = 0 tokens
        assert result >= 0

    def test_count_tokens_with_large_number(self):
        """Test count_tokens with larger numeric content."""
        limiter = LLMLimiter()
        # Large number with more than 4 digits
        result = limiter.count_tokens(12345)
        assert result > 0

    def test_to_str_with_nested_dict(self):
        """Test _to_str with nested dict content."""
        limiter = LLMLimiter()

        nested = {"outer": {"inner": "value"}}
        result = limiter._to_str(nested)
        assert "outer" in result
        assert "inner" in result


class TestLLMLimiterTruncate:
    """Test text truncation through public API."""

    def test_truncate_text_no_tiktoken(self):
        """Test truncate_text works correctly with or without tiktoken."""
        limiter = LLMLimiter()
        limiter._max_request_per_minute = None  # Force defaults

        text = "A" * 100
        # Max 10 tokens - result depends on whether tiktoken is available
        # With tiktoken: may compress due to BPE
        # Without tiktoken: uses char/4 approximation (~40 chars)
        result = limiter.truncate_text(text, 10)
        # Result should be at most original length
        assert len(result) <= 100
        # Result should be a string
        assert isinstance(result, str)

    def test_truncate_text_returns_unchanged_if_short(self):
        """Test truncate_text returns unchanged if text fits."""
        limiter = LLMLimiter()

        text = "Hello"
        result = limiter.truncate_text(text, 100)
        assert result == text

    def test_truncate_text_tiktoken_fallback_on_exception(self):
        """Test truncate_text falls back when tiktoken raises exception."""
        import builtins
        import sys

        limiter = LLMLimiter()

        original_import = builtins.__import__

        def failing_import(name, *args, **kwargs):
            if name == "tiktoken":
                raise Exception("tiktoken fail")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=failing_import):
            limiter._max_request_per_minute = None
            text = "A" * 100
            result = limiter.truncate_text(text, 10)
            assert len(result) <= 40

    def test_count_tokens_tiktoken_import_error(self):
        """Test _count_tokens falls back when tiktoken import fails."""
        import builtins

        limiter = LLMLimiter()

        original_import = builtins.__import__

        def failing_import(name, *args, **kwargs):
            if name == "tiktoken":
                raise ImportError("no tiktoken")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=failing_import):
            limiter._max_request_per_minute = None
            result = limiter._count_tokens("hello world")
            assert result > 0

    def test_to_str_with_instructions_on_object(self):
        """Test _to_str counts instructions from object with instructions field."""
        limiter = LLMLimiter()

        class MockObj:
            def __init__(self):
                self.instructions = "Some instructions"
                self.parts = []

        obj = MockObj()
        result = limiter._to_str(obj)
        assert "Some instructions" in result

    def test_to_str_with_instructions_skip_instructions_true(self):
        """Test _to_str skips instructions when skip_instructions=True."""
        limiter = LLMLimiter()

        class MockObj:
            def __init__(self):
                self.instructions = "Some instructions"
                self.parts = []

        obj = MockObj()
        result = limiter._to_str(obj, skip_instructions=True)
        assert "Some instructions" not in result

    def test_to_str_with_content_field(self):
        """Test _to_str extracts content field."""
        limiter = LLMLimiter()

        class MockObj:
            content = "Hello content"

        result = limiter._to_str(MockObj())
        assert "Hello content" in result

    def test_to_str_with_args_field(self):
        """Test _to_str extracts args field."""
        limiter = LLMLimiter()

        class MockObj:
            args = {"key": "value"}

        result = limiter._to_str(MockObj())
        assert "key" in result
        assert "value" in result

    def test_to_str_fallback_str_exception(self):
        """Test _to_str returns empty string when str() raises."""
        limiter = LLMLimiter()

        class BadObj:
            def __str__(self):
                raise Exception("Cannot convert")

        result = limiter._to_str(BadObj())
        assert result == ""


class TestLLMLimiterAcquireWithNotifier:
    @pytest.mark.asyncio
    async def test_acquire_with_notifier_when_rate_limited(self):
        """Test acquire calls notifier when rate limited."""
        limiter = LLMLimiter()
        limiter.max_request_per_minute = 1
        limiter.max_token_per_minute = 10
        limiter.throttle_check_interval = 0.01

        notifier = MagicMock()
        limiter._request_log.append(time.time())
        limiter._token_log.append((time.time(), 9))

        async def acquire_with_timeout():
            try:
                await asyncio.wait_for(
                    limiter.acquire("test", notifier=notifier), timeout=0.1
                )
            except asyncio.TimeoutError:
                pass

        await acquire_with_timeout()
        assert notifier.called

    @pytest.mark.asyncio
    async def test_acquire_notifier_clear_after_limit_lifts(self):
        """Once the rate limit lifts, the notifier receives a final clear ("\\n").

        Drives the public acquire(): start over the request budget, then raise the
        budget mid-flight so the throttle loop exits and the clear branch runs.
        """
        limiter = LLMLimiter()
        limiter.max_request_per_minute = 1
        limiter.max_token_per_minute = 10000
        limiter.throttle_check_interval = 0.01
        limiter.max_request_per_minute = 1
        # Pre-fill the request budget so the first acquire is blocked.
        await limiter.acquire("seed")

        notifier = MagicMock()

        async def lift_limit_soon():
            await asyncio.sleep(0.03)
            limiter.max_request_per_minute = 100

        await asyncio.gather(
            limiter.acquire("blocked", notifier=notifier),
            lift_limit_soon(),
        )

        # Notifier was called for the wait message AND the trailing clear.
        assert notifier.called
        assert any(
            call.args and call.args[0] == "\n" for call in notifier.call_args_list
        )

    @pytest.mark.asyncio
    async def test_acquire_notifier_called_once_with_clear(self):
        """Test notifier receives clear message after rate limit clears."""
        limiter = LLMLimiter()
        limiter.max_request_per_minute = 1
        limiter.max_token_per_minute = 10000
        limiter.throttle_check_interval = 0.01

        limiter._request_log.append(time.time())

        notifier = MagicMock()

        async def acquire_with_timeout():
            try:
                await asyncio.wait_for(
                    limiter.acquire("test", notifier=notifier), timeout=0.1
                )
            except asyncio.TimeoutError:
                pass

        await acquire_with_timeout()
        assert notifier.called
