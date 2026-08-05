from unittest.mock import AsyncMock, MagicMock

import pytest

from zrb.config.config import CFG
from zrb.llm.tool_call.tool_policy.repetition_state import reset_repetition_state
from zrb.llm.tool_call.tool_policy.repetition_validation import repetition_policy


@pytest.fixture(autouse=True)
def _clean_state():
    reset_repetition_state()
    yield
    reset_repetition_state()


def _call(command: str, tool_name: str = "Shell") -> MagicMock:
    call = MagicMock()
    call.tool_name = tool_name
    call.args = {"command": command}
    return call


async def _run(policy, command: str, result: str = "output", tool_name: str = "Shell"):
    return await policy(
        MagicMock(), _call(command, tool_name), AsyncMock(return_value=result)
    )


@pytest.mark.asyncio
async def test_the_first_attempts_are_left_alone():
    """Re-running a test suite twice is ordinary; only a loop is worth naming."""
    policy = repetition_policy()

    first = await _run(policy, "pytest")
    second = await _run(policy, "pytest")

    assert first == "output"
    assert second == "output"


@pytest.mark.asyncio
async def test_the_third_identical_attempt_is_flagged():
    """workflow.md says change what you are testing by the third try."""
    policy = repetition_policy()

    for _ in range(2):
        await _run(policy, "python main.py")
    third = await _run(policy, "python main.py")

    assert "attempt 3 at the same command" in third
    assert "stop and report" in third


@pytest.mark.asyncio
async def test_the_nudge_fires_once_not_on_every_later_call():
    """One loop earns one escalation; nagging would just add noise to it."""
    policy = repetition_policy()

    for _ in range(3):
        await _run(policy, "python main.py")
    fourth = await _run(policy, "python main.py")

    assert "[SYSTEM SUGGESTION]" not in fourth


@pytest.mark.asyncio
async def test_a_changed_command_is_not_a_repeat():
    """Varying the command IS changing what you test — the desired behaviour."""
    policy = repetition_policy()

    await _run(policy, "pytest test_a.py")
    await _run(policy, "pytest test_b.py")
    third = await _run(policy, "pytest test_c.py")

    assert "[SYSTEM SUGGESTION]" not in third


@pytest.mark.asyncio
async def test_the_call_is_never_blocked():
    """The command still runs; only the result gains an observation."""
    policy = repetition_policy()

    for _ in range(2):
        await _run(policy, "make build")
    third = await _run(policy, "make build", result="BUILD OK")

    assert third.startswith("BUILD OK")


@pytest.mark.asyncio
async def test_disabling_the_threshold_turns_it_off(monkeypatch):
    monkeypatch.setattr(CFG, "LLM_REPEATED_ATTEMPT_THRESHOLD", 0)
    policy = repetition_policy()

    for _ in range(5):
        result = await _run(policy, "python main.py")

    assert result == "output"


@pytest.mark.asyncio
async def test_untracked_tools_pass_through():
    policy = repetition_policy()

    for _ in range(5):
        result = await _run(policy, "anything", tool_name="Read")

    assert result == "output"


@pytest.mark.asyncio
async def test_json_encoded_args_are_counted(monkeypatch):
    """pydantic-ai hands args through as a JSON string for some providers."""
    policy = repetition_policy()
    call = MagicMock()
    call.tool_name = "Shell"
    call.args = '{"command": "python main.py"}'

    for _ in range(2):
        await policy(MagicMock(), call, AsyncMock(return_value="out"))
    third = await policy(MagicMock(), call, AsyncMock(return_value="out"))

    assert "attempt 3 at the same command" in third


@pytest.mark.parametrize(
    "args",
    ["not json", 12345, {"no_command_key": "x"}, {"command": ""}],
    ids=["unparseable", "not-a-mapping", "no-command", "empty-command"],
)
@pytest.mark.asyncio
async def test_args_without_a_usable_command_pass_through(args):
    """No signature means nothing to count; the call must still run."""
    policy = repetition_policy()
    call = MagicMock()
    call.tool_name = "Shell"
    call.args = args

    for _ in range(5):
        result = await policy(MagicMock(), call, AsyncMock(return_value="out"))

    assert result == "out"


@pytest.mark.asyncio
async def test_a_non_string_result_is_returned_unchanged():
    """Only a text result can carry the note; anything else stays intact."""
    policy = repetition_policy()
    sentinel = {"structured": True}

    for _ in range(2):
        await _run(policy, "python main.py")
    third = await policy(
        MagicMock(), _call("python main.py"), AsyncMock(return_value=sentinel)
    )

    assert third is sentinel
