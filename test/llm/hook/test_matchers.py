import json
from unittest.mock import MagicMock, patch

import pytest

from zrb.llm.hook.interface import HookResult
from zrb.llm.hook.manager import HookManager
from zrb.llm.hook.types import HookEvent


def _create_mock_cfg():
    """Create mock config for tests."""
    mock_cfg = MagicMock()
    mock_cfg.LLM_INCLUDE_JOURNAL = False
    mock_cfg.ROOT_GROUP_NAME = "zrb"
    mock_cfg.LLM_PLUGIN_DIRS = []
    mock_cfg.HOOKS_DIRS = []
    mock_cfg.LLM_JOURNAL_DIR = "/tmp/test_journal"
    mock_cfg.LLM_JOURNAL_INDEX_FILE = "index.md"
    return mock_cfg


@pytest.fixture
def hook_manager():
    # Patch CFG in all modules that import it
    mock_cfg = _create_mock_cfg()
    with patch("zrb.llm.hook.manager.CFG", mock_cfg), patch(
        "zrb.llm.hook.journal.CFG", mock_cfg
    ):
        return HookManager()


async def check_match(tmp_path, matchers, context_data):
    """Helper to verify if matchers work using public scan + execute_hooks."""
    hook_dir = tmp_path / "hooks"
    if hook_dir.exists():
        import shutil

        shutil.rmtree(hook_dir)
    hook_dir.mkdir()

    hook_file = hook_dir / "test.json"
    hook_content = [
        {
            "name": "test-hook",
            "events": ["SessionStart"],
            "type": "command",
            "config": {"command": "echo matched"},
            "matchers": matchers,
        }
    ]
    with open(hook_file, "w") as f:
        json.dump(hook_content, f)

    mock_cfg = _create_mock_cfg()
    with patch("zrb.llm.hook.manager.CFG", mock_cfg), patch(
        "zrb.llm.hook.journal.CFG", mock_cfg
    ):
        manager = HookManager()
        manager.scan(search_dirs=[str(hook_dir)])

        # Extract event_data if present, otherwise use None
        data_to_pass = context_data.copy()
        event_data = data_to_pass.pop("event_data", None)

        # Pass context_data as kwargs so they populate HookContext attributes
        results = await manager.execute_hooks(
            HookEvent.SESSION_START, event_data, **data_to_pass
        )
        # If the hook matched, it should have been executed and returned a result that isn't "Skipped due to matchers"
        for result in results:
            if result.message != "Skipped due to matchers":
                return True
    return False


@pytest.mark.asyncio
async def test_evaluate_matchers_equals(tmp_path):
    # Match
    matchers = [{"field": "event_data.tool", "operator": "equals", "value": "bash"}]
    assert (
        await check_match(tmp_path, matchers, {"event_data": {"tool": "bash"}}) is True
    )

    # No Match
    matchers = [{"field": "event_data.tool", "operator": "equals", "value": "python"}]
    assert (
        await check_match(tmp_path, matchers, {"event_data": {"tool": "bash"}}) is False
    )


@pytest.mark.asyncio
async def test_evaluate_matchers_not_equals(tmp_path):
    # Match
    matchers = [
        {"field": "event_data.tool", "operator": "not_equals", "value": "python"}
    ]
    assert (
        await check_match(tmp_path, matchers, {"event_data": {"tool": "bash"}}) is True
    )

    # No Match
    matchers = [{"field": "event_data.tool", "operator": "not_equals", "value": "bash"}]
    assert (
        await check_match(tmp_path, matchers, {"event_data": {"tool": "bash"}}) is False
    )


@pytest.mark.asyncio
async def test_evaluate_matchers_contains(tmp_path):
    # Match
    matchers = [{"field": "prompt", "operator": "contains", "value": "world"}]
    assert await check_match(tmp_path, matchers, {"prompt": "hello world"}) is True

    # No Match
    matchers = [{"field": "prompt", "operator": "contains", "value": "mars"}]
    assert await check_match(tmp_path, matchers, {"prompt": "hello world"}) is False


@pytest.mark.asyncio
async def test_evaluate_matchers_starts_with(tmp_path):
    # Match
    matchers = [{"field": "prompt", "operator": "starts_with", "value": "hello"}]
    assert await check_match(tmp_path, matchers, {"prompt": "hello world"}) is True

    # No Match
    matchers = [{"field": "prompt", "operator": "starts_with", "value": "world"}]
    assert await check_match(tmp_path, matchers, {"prompt": "hello world"}) is False


@pytest.mark.asyncio
async def test_evaluate_matchers_ends_with(tmp_path):
    # Match
    matchers = [{"field": "prompt", "operator": "ends_with", "value": "world"}]
    assert await check_match(tmp_path, matchers, {"prompt": "hello world"}) is True

    # No Match
    matchers = [{"field": "prompt", "operator": "ends_with", "value": "hello"}]
    assert await check_match(tmp_path, matchers, {"prompt": "hello world"}) is False


@pytest.mark.asyncio
async def test_evaluate_matchers_regex(tmp_path):
    # Match
    matchers = [
        {"field": "prompt", "operator": "regex", "value": "error: .* not found"}
    ]
    assert (
        await check_match(tmp_path, matchers, {"prompt": "error: file not found"})
        is True
    )

    # No Match
    matchers = [{"field": "prompt", "operator": "regex", "value": "^success"}]
    assert (
        await check_match(tmp_path, matchers, {"prompt": "error: file not found"})
        is False
    )


@pytest.mark.asyncio
async def test_evaluate_matchers_glob(tmp_path):
    # Match
    matchers = [{"field": "tool_name", "operator": "glob", "value": "*.py"}]
    assert await check_match(tmp_path, matchers, {"tool_name": "script.py"}) is True

    # No Match
    matchers = [{"field": "tool_name", "operator": "glob", "value": "*.js"}]
    assert await check_match(tmp_path, matchers, {"tool_name": "script.py"}) is False


@pytest.mark.asyncio
async def test_evaluate_matchers_case_sensitivity(tmp_path):
    # Case Insensitive Match
    matchers = [
        {
            "field": "prompt",
            "operator": "equals",
            "value": "hello world",
            "case_sensitive": False,
        }
    ]
    assert await check_match(tmp_path, matchers, {"prompt": "Hello World"}) is True

    # Case Sensitive Match Fail
    matchers = [
        {
            "field": "prompt",
            "operator": "equals",
            "value": "hello world",
            "case_sensitive": True,
        }
    ]
    assert await check_match(tmp_path, matchers, {"prompt": "Hello World"}) is False


@pytest.mark.asyncio
async def test_evaluate_matchers_nested_field_missing(tmp_path):
    # Field missing
    matchers = [
        {"field": "event_data.missing_key", "operator": "equals", "value": "value"}
    ]
    assert await check_match(tmp_path, matchers, {"event_data": {}}) is False


@pytest.mark.asyncio
async def test_evaluate_matchers_multiple(tmp_path):
    # All match
    matchers = [
        {"field": "tool_name", "operator": "equals", "value": "bash"},
        {"field": "prompt", "operator": "contains", "value": "rm"},
    ]
    assert (
        await check_match(tmp_path, matchers, {"tool_name": "bash", "prompt": "rm -rf"})
        is True
    )

    # One fails
    matchers = [
        {"field": "tool_name", "operator": "equals", "value": "bash"},
        {"field": "prompt", "operator": "contains", "value": "safe_command"},
    ]
    assert (
        await check_match(tmp_path, matchers, {"tool_name": "bash", "prompt": "rm -rf"})
        is False
    )


class TestHookEventFromClaudeString:
    """Tests for HookEvent.from_claude_string class method."""

    def test_exact_match(self):
        """Test direct enum value lookup."""
        from zrb.llm.hook.types import HookEvent

        result = HookEvent.from_claude_string("SessionStart")
        assert result == HookEvent.SESSION_START

    def test_case_insensitive_fallback(self):
        """Test case-insensitive fallback when exact match fails."""
        from zrb.llm.hook.types import HookEvent

        result = HookEvent.from_claude_string("SESSIONSTART")
        assert result == HookEvent.SESSION_START

    def test_unknown_value_raises(self):
        """Test that unknown values raise ValueError."""
        from zrb.llm.hook.types import HookEvent

        with pytest.raises(ValueError, match="Unknown hook event"):
            HookEvent.from_claude_string("NonExistentEvent")


class TestMatcherOperatorFromClaudePattern:
    """Tests for MatcherOperator.from_claude_pattern class method."""

    def test_wildcard_returns_glob(self):
        """Test that '*' returns GLOB."""
        from zrb.llm.hook.types import MatcherOperator

        assert MatcherOperator.from_claude_pattern("*") == MatcherOperator.GLOB

    def test_empty_string_returns_glob(self):
        """Test that empty string returns GLOB."""
        from zrb.llm.hook.types import MatcherOperator

        assert MatcherOperator.from_claude_pattern("") == MatcherOperator.GLOB

    def test_glob_pattern_returns_glob(self):
        """Test that patterns with wildcards return GLOB."""
        from zrb.llm.hook.types import MatcherOperator

        assert MatcherOperator.from_claude_pattern("*.py") == MatcherOperator.GLOB
        assert MatcherOperator.from_claude_pattern("file?.txt") == MatcherOperator.GLOB

    def test_regex_pattern_with_anchor_returns_regex(self):
        """Test that anchored patterns return REGEX."""
        from zrb.llm.hook.types import MatcherOperator

        assert MatcherOperator.from_claude_pattern("^start") == MatcherOperator.REGEX
        assert MatcherOperator.from_claude_pattern("end$") == MatcherOperator.REGEX

    def test_dot_star_in_pattern_returns_glob_due_to_star(self):
        """Test that patterns with '.*' return GLOB (star is checked first)."""
        from zrb.llm.hook.types import MatcherOperator

        # The glob check (contains '*') fires before the regex check
        assert MatcherOperator.from_claude_pattern("foo.*bar") == MatcherOperator.GLOB

    def test_plain_string_returns_equals(self):
        """Test that plain strings return EQUALS."""
        from zrb.llm.hook.types import MatcherOperator

        assert MatcherOperator.from_claude_pattern("bash") == MatcherOperator.EQUALS
        assert (
            MatcherOperator.from_claude_pattern("exact_match") == MatcherOperator.EQUALS
        )
