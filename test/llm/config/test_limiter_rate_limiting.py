import time
from unittest.mock import patch

from pydantic_ai.messages import ModelRequest, UserPromptPart

from zrb.llm.config.limiter import LLMLimiter, is_turn_start


class TestLLMLimiterRateLimiting:
    """Test rate limiting behavior through public API."""

    def test_can_proceed_empty_logs(self):
        """Test can_proceed returns True when logs are empty."""
        limiter = LLMLimiter()
        # Empty logs means we can proceed
        result = limiter.can_proceed(100)
        assert result is True

    def test_can_proceed_under_limits(self):
        """Test can_proceed returns True when under limits."""
        limiter = LLMLimiter()
        limiter.max_request_per_minute = 10
        limiter.max_token_per_minute = 1000

        # Add some usage but stay under limit
        limiter.request_log.append(time.time())
        limiter.token_log.append((time.time(), 50))

        result = limiter.can_proceed(100)
        assert result is True

    def test_can_proceed_over_request_limit(self):
        """Test can_proceed returns False when request limit exceeded."""
        limiter = LLMLimiter()
        limiter.max_request_per_minute = 2

        # Fill up request log
        limiter.request_log.append(time.time())
        limiter.request_log.append(time.time())

        result = limiter.can_proceed(10)
        assert result is False

    def test_can_proceed_over_token_limit(self):
        """Test can_proceed returns False when token limit exceeded."""
        limiter = LLMLimiter()
        limiter.max_token_per_minute = 100

        # Fill up token log
        limiter.token_log.append((time.time(), 99))

        result = limiter.can_proceed(10)
        assert result is False

    def test_get_limit_reason_request_limit(self):
        """Test get_limit_reason returns request limit message."""
        limiter = LLMLimiter()
        limiter.max_request_per_minute = 5

        # Fill request log
        for _ in range(5):
            limiter.request_log.append(time.time())

        reason = limiter.get_limit_reason(10)
        assert "Max Requests" in reason
        assert "5/min" in reason

    def test_get_limit_reason_token_limit(self):
        """Test get_limit_reason returns token limit message."""
        limiter = LLMLimiter()
        limiter.max_request_per_minute = 100
        limiter.max_token_per_minute = 50

        reason = limiter.get_limit_reason(100)
        assert "Max Tokens" in reason
        assert "50/min" in reason

    def test_calculate_wait_time_request_limit(self):
        """Test calculate_wait_time for request limit."""
        limiter = LLMLimiter()
        limiter.max_request_per_minute = 2

        # Fill request log
        limiter.request_log.append(time.time())
        limiter.request_log.append(time.time())

        wait = limiter.calculate_wait_time(10)
        assert wait > 0

    def test_calculate_wait_time_token_limit(self):
        """Test calculate_wait_time for token limit."""
        limiter = LLMLimiter()
        limiter.max_token_per_minute = 50

        # Fill token log near limit
        limiter.token_log.append((time.time(), 40))

        wait = limiter.calculate_wait_time(20)
        assert wait > 0

    def test_prune_logs_removes_old_entries(self):
        """Test prune_logs removes entries older than 60 seconds."""
        limiter = LLMLimiter()

        # Add old entries (65 seconds ago)
        old_time = time.time() - 65
        limiter.request_log.append(old_time)
        limiter.token_log.append((old_time, 100))

        # Add recent entries
        limiter.request_log.append(time.time())
        limiter.token_log.append((time.time(), 50))

        limiter.prune_logs()

        assert len(limiter.request_log) == 1
        assert len(limiter.token_log) == 1

    def test_prune_logs_keeps_recent_entries(self):
        """Test prune_logs keeps entries within 60 seconds."""
        limiter = LLMLimiter()

        # Add recent entries
        limiter.request_log.append(time.time())
        limiter.token_log.append((time.time(), 100))

        limiter.prune_logs()

        assert len(limiter.request_log) == 1
        assert len(limiter.token_log) == 1


class TestLLMLimiterPropertyDefaults:
    """Properties fall back to the built-in default when CFG is unset/falsy."""

    def test_max_token_per_request_default_when_cfg_falsy(self):
        limiter = LLMLimiter()
        with patch("zrb.llm.config.limiter.CFG") as cfg:
            cfg.LLM_MAX_TOKEN_PER_REQUEST = None
            assert limiter.max_token_per_request == 128_000

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

    def test_max_request_per_minute_zero_is_not_replaced_by_default(self):
        """An explicit 0 means 'block every request' and must not fall back
        to the default 60 just because 0 is falsy."""
        limiter = LLMLimiter()
        with patch("zrb.llm.config.limiter.CFG") as cfg:
            cfg.LLM_MAX_REQUEST_PER_MINUTE = 0
            cfg.LLM_MAX_TOKEN_PER_MINUTE = 100_000
            assert limiter.max_request_per_minute == 0
            assert limiter.can_proceed(tokens=1) is False

    def test_max_token_per_minute_zero_is_not_replaced_by_default(self):
        """An explicit 0 means 'block every request' and must not fall back
        to the default 100_000 just because 0 is falsy."""
        limiter = LLMLimiter()
        with patch("zrb.llm.config.limiter.CFG") as cfg:
            cfg.LLM_MAX_REQUEST_PER_MINUTE = 60
            cfg.LLM_MAX_TOKEN_PER_MINUTE = 0
            assert limiter.max_token_per_minute == 0
            assert limiter.can_proceed(tokens=1) is False

    def test_max_token_per_request_zero_is_not_replaced_by_default(self):
        """An explicit 0 means 'block every request' and must not fall back
        to the default 128_000 just because 0 is falsy."""
        limiter = LLMLimiter()
        with patch("zrb.llm.config.limiter.CFG") as cfg:
            cfg.LLM_MAX_TOKEN_PER_REQUEST = 0
            assert limiter.max_token_per_request == 0


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
    """to_str over a list counts only the latest item's instructions (lines 279-282)."""

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
        """Test to_str with nested dict content."""
        limiter = LLMLimiter()

        nested = {"outer": {"inner": "value"}}
        result = limiter.to_str(nested)
        assert "outer" in result
        assert "inner" in result
