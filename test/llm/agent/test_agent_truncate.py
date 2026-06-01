"""Tests for the global tool-result truncation backstop."""

from contextlib import contextmanager
from unittest.mock import patch

import pytest

from zrb.llm.agent.truncate import truncate_tool_content


@contextmanager
def cap_at(limit: int):
    """Patch CFG so the wrapper reads a known tool-result char cap."""
    with patch("zrb.llm.agent.common.CFG") as mock_cfg:
        mock_cfg.LLM_MAX_TOOL_RESULT_CHARS = limit
        yield


def test_below_limit_unchanged():
    content = "a" * 100
    out, truncated = truncate_tool_content(content, limit=1000)
    assert out == content
    assert truncated is False


def test_at_limit_unchanged():
    content = "a" * 50
    out, truncated = truncate_tool_content(content, limit=50)
    assert out == content
    assert truncated is False


def test_above_limit_truncated_head_and_tail():
    content = "HEAD" + ("x" * 1000) + "TAIL"
    out, truncated = truncate_tool_content(content, limit=100)
    assert truncated is True
    assert out.startswith("HEAD")
    assert out.endswith("TAIL")
    assert "truncated" in out
    # head + tail kept characters total the limit (marker is extra)
    assert "Re-read a narrower slice" in out


def test_limit_zero_disables():
    content = "a" * 10_000
    out, truncated = truncate_tool_content(content, limit=0)
    assert out == content
    assert truncated is False


def test_limit_none_disables():
    content = "a" * 10_000
    out, truncated = truncate_tool_content(content, limit=None)
    assert out == content
    assert truncated is False


def test_negative_limit_disables():
    content = "a" * 10_000
    out, truncated = truncate_tool_content(content, limit=-5)
    assert out == content
    assert truncated is False


def test_non_string_passthrough():
    out, truncated = truncate_tool_content(12345, limit=1)  # type: ignore[arg-type]
    assert out == 12345
    assert truncated is False


@pytest.mark.asyncio
async def test_wrapper_truncates_large_string_content():
    from pydantic_ai import ToolReturn

    from zrb.llm.agent.common import create_safe_wrapper

    big = "z" * 5000

    def tool():
        return big

    with cap_at(1000):
        wrapped = create_safe_wrapper(tool)
        result = await wrapped()

    assert isinstance(result, ToolReturn)
    assert result.metadata.get("truncated") is True
    assert result.metadata.get("original_chars") == 5000
    assert len(result.content) < 5000
    # return_value is left whole — programmatic consumers unaffected
    assert result.return_value == big


@pytest.mark.asyncio
async def test_wrapper_does_not_truncate_small_content():
    from pydantic_ai import ToolReturn

    from zrb.llm.agent.common import create_safe_wrapper

    def tool():
        return "small"

    with cap_at(1000):
        wrapped = create_safe_wrapper(tool)
        result = await wrapped()

    assert isinstance(result, ToolReturn)
    assert result.content == "small"
    assert "truncated" not in result.metadata


@pytest.mark.asyncio
async def test_wrapper_respects_explicit_toolreturn():
    """A tool returning its own ToolReturn is passed through untouched."""
    from pydantic_ai import ToolReturn

    from zrb.llm.agent.common import create_safe_wrapper

    big = "q" * 5000

    def tool():
        return ToolReturn(return_value=big, content=big)

    with cap_at(10):
        wrapped = create_safe_wrapper(tool)
        result = await wrapped()

    assert result.content == big  # not re-truncated
