from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic_ai import ToolDenied

from zrb.llm.tool.file_freshness import reset_file_freshness
from zrb.llm.tool_call.tool_policy.write_freshness_validation import (
    write_freshness_policy,
)


@pytest.fixture(autouse=True)
def _clean_state():
    reset_file_freshness()
    yield
    reset_file_freshness()


def _call(tool_name: str, path: str) -> MagicMock:
    call = MagicMock()
    call.tool_name = tool_name
    call.args = {"path": path}
    return call


async def _run(policy, tool_name: str, path: str, result: str = "ok"):
    return await policy(
        MagicMock(), _call(tool_name, path), AsyncMock(return_value=result)
    )


@pytest.mark.asyncio
async def test_creating_a_new_file_is_never_blocked(tmp_path):
    """There is nothing to be stale about when the path does not exist yet."""
    policy = write_freshness_policy()

    result = await _run(policy, "Write", str(tmp_path / "new.py"))

    assert result == "ok"


@pytest.mark.asyncio
async def test_overwriting_an_unread_file_is_refused(tmp_path):
    """A whole-file write replaces content the call itself never names."""
    target = tmp_path / "existing.py"
    target.write_text("important = True\n")
    policy = write_freshness_policy()

    result = await _run(policy, "Write", str(target))

    assert isinstance(result, ToolDenied)
    assert "have not read it" in result.message
    assert "Edit" in result.message


@pytest.mark.asyncio
async def test_write_is_allowed_after_reading(tmp_path):
    target = tmp_path / "existing.py"
    target.write_text("important = True\n")
    policy = write_freshness_policy()

    await _run(policy, "Read", str(target))
    result = await _run(policy, "Write", str(target))

    assert result == "ok"


@pytest.mark.asyncio
async def test_an_edit_makes_a_later_blind_write_stale(tmp_path):
    """The regression this policy exists for.

    A trial read worker.py, edited it, got a [DIAGNOSTIC], and rewrote the whole
    file from memory — reverting the edit and shipping an infinite loop. It had
    read the file, so read-before-write alone would have allowed it. The read
    has to postdate the change.
    """
    target = tmp_path / "worker.py"
    target.write_text("def run():\n    return\n")
    policy = write_freshness_policy()

    await _run(policy, "Read", str(target))
    await _run(policy, "Edit", str(target))
    result = await _run(policy, "Write", str(target))

    assert isinstance(result, ToolDenied)
    assert "changed since you last read it" in result.message


@pytest.mark.asyncio
async def test_rereading_clears_staleness(tmp_path):
    target = tmp_path / "worker.py"
    target.write_text("def run():\n    return\n")
    policy = write_freshness_policy()

    await _run(policy, "Read", str(target))
    await _run(policy, "Edit", str(target))
    await _run(policy, "Read", str(target))
    result = await _run(policy, "Write", str(target))

    assert result == "ok"


@pytest.mark.asyncio
async def test_consecutive_writes_are_allowed(tmp_path):
    """The model authored every byte of the previous write; its memory is the file."""
    target = tmp_path / "gen.py"
    policy = write_freshness_policy()

    await _run(policy, "Write", str(target))
    target.write_text("generated\n")
    result = await _run(policy, "Write", str(target))

    assert result == "ok"


@pytest.mark.asyncio
async def test_edit_is_never_gated(tmp_path):
    """old_text already fails loudly on drift; a precondition would be friction."""
    target = tmp_path / "untouched.py"
    target.write_text("x = 1\n")
    policy = write_freshness_policy()

    result = await _run(policy, "Edit", str(target))

    assert result == "ok"


@pytest.mark.asyncio
async def test_a_refused_read_does_not_count_as_having_seen_the_file(tmp_path):
    """Recording happens after the chain, so a denied Read grants nothing."""
    target = tmp_path / "existing.py"
    target.write_text("data\n")
    policy = write_freshness_policy()

    await _run(policy, "Read", str(target), result=ToolDenied("nope"))
    result = await _run(policy, "Write", str(target))

    assert isinstance(result, ToolDenied)
    assert "have not read it" in result.message


@pytest.mark.asyncio
async def test_unrelated_tools_pass_through():
    policy = write_freshness_policy()
    call = MagicMock()
    call.tool_name = "Shell"
    call.args = {"command": "ls"}

    result = await policy(MagicMock(), call, AsyncMock(return_value="passed"))

    assert result == "passed"


@pytest.mark.asyncio
async def test_a_call_without_a_path_passes_through():
    policy = write_freshness_policy()
    call = MagicMock()
    call.tool_name = "Write"
    call.args = "not json at all"

    result = await policy(MagicMock(), call, AsyncMock(return_value="passed"))

    assert result == "passed"


@pytest.mark.asyncio
async def test_json_encoded_args_are_understood(tmp_path):
    """pydantic-ai hands args through as a JSON string for some providers."""
    target = tmp_path / "existing.py"
    target.write_text("data\n")
    policy = write_freshness_policy()
    call = MagicMock()
    call.tool_name = "Write"
    call.args = f'{{"path": "{target}", "content": "x"}}'

    result = await policy(MagicMock(), call, AsyncMock(return_value="ok"))

    assert isinstance(result, ToolDenied)
