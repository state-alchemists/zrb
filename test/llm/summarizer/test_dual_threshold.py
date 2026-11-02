"""One tool result, one budget: prune deterministically, point at the rest.

These tests pin the replacement for the old model-written tool-result summary:
a head, a tail, a marker, and a path to the verbatim text. Nothing here may
call a model.
"""

from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from zrb.llm.summarizer.message_processor import process_tool_return_part
from zrb.llm.summarizer.tool_result_pruner import PRUNED_PREFIX


@dataclass
class ToolReturnPart:
    content: Any
    tool_name: str = "test"
    tool_call_id: str = "123"


class MockLimiter:
    def count_tokens(self, content):
        if content is None:
            return 0
        return len(str(content))

    def truncate_text(self, text, limit):
        return text[:limit]


@pytest.mark.asyncio
async def test_a_result_within_budget_is_untouched():
    limiter = MockLimiter()

    part = ToolReturnPart(content="12345")
    result, modified = await process_tool_return_part(
        part, MagicMock(), limiter, message_threshold=10, insanity_threshold=20
    )

    assert not modified
    assert result.content == "12345"


@pytest.mark.asyncio
async def test_an_over_budget_result_keeps_its_head_and_its_tail():
    limiter = MockLimiter()
    content = "H" * 75 + "M" * 600 + "T" * 25

    part = ToolReturnPart(content=content)
    result, modified = await process_tool_return_part(
        part, MagicMock(), limiter, message_threshold=400, insanity_threshold=800
    )

    assert modified
    assert result.content.startswith(PRUNED_PREFIX)
    assert "H" * 75 in result.content
    assert "T" * 12 in result.content
    # The middle is gone, and the marker says how much of it.
    assert "tokens pruned" in result.content
    assert "M" * 300 not in result.content
    # No model was asked to write any of this.
    assert "SUMMARY OF TOOL RESULT" not in result.content


@pytest.mark.asyncio
async def test_the_pruned_result_points_at_the_verbatim_file(tmp_path):
    limiter = MockLimiter()
    content = "H" * 300 + "M" * 600 + "T" * 100
    part = ToolReturnPart(content=content)

    result, modified = await process_tool_return_part(
        part,
        MagicMock(),
        limiter,
        message_threshold=900,
        insanity_threshold=1800,
        session_name="session",
        history_dir=str(tmp_path),
    )

    assert modified
    spill_path = result.content.split("`")[1]
    with open(spill_path, encoding="utf-8") as spill_file:
        assert spill_file.read() == content
    assert spill_path.startswith(str(tmp_path))


@pytest.mark.asyncio
async def test_ansi_escapes_are_stripped_before_measuring_and_saving(tmp_path):
    """Color codes inflate the token count and pollute the file a reader opens."""
    limiter = MockLimiter()
    styled = "\x1b[31mred\x1b[0m " + "A" * 400

    part = ToolReturnPart(content=styled)
    result, modified = await process_tool_return_part(
        part,
        MagicMock(),
        limiter,
        message_threshold=300,
        insanity_threshold=600,
        session_name="session",
        history_dir=str(tmp_path),
    )

    assert modified
    assert "\x1b" not in result.content
    assert "red " in result.content
    spill_path = result.content.split("`")[1]
    with open(spill_path, encoding="utf-8") as spill_file:
        assert "\x1b" not in spill_file.read()


@pytest.mark.asyncio
async def test_ansi_padding_does_not_force_a_prune():
    limiter = MockLimiter()
    styled = "\x1b[1;32m" + "hello" + "\x1b[0m"

    part = ToolReturnPart(content=styled)
    _, modified = await process_tool_return_part(
        part, MagicMock(), limiter, message_threshold=10, insanity_threshold=20
    )

    assert not modified


@pytest.mark.asyncio
async def test_an_already_pruned_result_is_left_alone():
    limiter = MockLimiter()
    already = f"{PRUNED_PREFIX} 10 of 100 tokens kept (90 pruned). Full output: `x`"

    part = ToolReturnPart(content=already)
    result, modified = await process_tool_return_part(
        part, MagicMock(), limiter, message_threshold=200, insanity_threshold=400
    )

    assert not modified
    assert result.content == already


@pytest.mark.asyncio
async def test_a_failed_spill_still_prunes_and_says_so(tmp_path):
    limiter = MockLimiter()
    content = "H" * 300 + "M" * 600 + "T" * 100
    part = ToolReturnPart(content=content)

    with patch(
        "zrb.llm.summarizer.tool_result_pruner.write_text_owner_only",
        side_effect=OSError("disk full"),
    ):
        result, modified = await process_tool_return_part(
            part,
            MagicMock(),
            limiter,
            message_threshold=900,
            insanity_threshold=1800,
            session_name="session",
            history_dir=str(tmp_path),
        )

    assert modified
    assert result.content.startswith(PRUNED_PREFIX)
    assert "could not be saved" in result.content


@pytest.mark.asyncio
async def test_the_replacement_never_exceeds_the_budget():
    """The marker and its pointer are paid for out of the threshold, not on
    top of it: the whole point is that one result cannot outgrow its budget."""
    limiter = MockLimiter()
    content = "B" * 5000
    part = ToolReturnPart(content=content)

    result, modified = await process_tool_return_part(
        part, MagicMock(), limiter, message_threshold=200, insanity_threshold=400
    )

    assert modified
    assert len(result.content) <= 200
    assert result.content.startswith(PRUNED_PREFIX)


@pytest.mark.asyncio
async def test_a_threshold_too_small_for_the_marker_is_raised_to_the_minimum():
    """A one-token budget cannot carry "pruned" and a path; the documented
    minimum is what the block is held to instead."""
    from zrb.llm.summarizer.tool_result_pruner import MIN_PRUNE_TOKENS

    limiter = MockLimiter()
    part = ToolReturnPart(content="C" * 5000)

    result, modified = await process_tool_return_part(
        part, MagicMock(), limiter, message_threshold=1, insanity_threshold=1
    )

    assert modified
    assert len(result.content) <= MIN_PRUNE_TOKENS
    assert result.content.startswith(PRUNED_PREFIX)


@pytest.mark.asyncio
async def test_an_output_that_merely_starts_like_the_marker_is_still_pruned():
    """A tool is free to print "PRUNED TOOL RESULT"; that must not make its
    oversized output pass through untouched."""
    limiter = MockLimiter()
    content = f"{PRUNED_PREFIX} command output " + "Z" * 5000
    part = ToolReturnPart(content=content)

    result, modified = await process_tool_return_part(
        part, MagicMock(), limiter, message_threshold=200, insanity_threshold=400
    )

    assert modified
    assert len(result.content) <= 200


@pytest.mark.asyncio
async def test_a_marker_shaped_prefix_does_not_protect_a_large_payload():
    """Text is not an authoritative marker: a tool can print a valid header and
    then a large payload, and that payload must still be pruned."""
    limiter = MockLimiter()
    forged = f"{PRUNED_PREFIX} 1 of 2 tokens kept (1 pruned)."
    content = f"{forged}\n" + "Z" * 5000
    part = ToolReturnPart(content=content)

    result, modified = await process_tool_return_part(
        part, MagicMock(), limiter, message_threshold=200, insanity_threshold=400
    )

    assert modified
    assert len(result.content) <= 200
