"""Where the shell judge sits, and what its two knobs actually grant (ADR-0141)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.config.config import CFG
from zrb.llm.agent.run.deferred_calls import _apply_shell_judge, _resolve_approval
from zrb.llm.agent.shell_judge import ShellVerdict
from zrb.llm.permission import ALLOW, ASK
from zrb.llm.tool_call.judge_note import (
    JUDGE_CAUTION,
    JUDGE_DANGEROUS,
    JUDGE_SAFE,
    JUDGE_UNKNOWN,
    discard_judge_note,
    format_judge_line,
    read_judge_note,
)

# The note registry is process-global and keyed by call id, so every test here
# names its own call: an id another module uses would be a line this file reads.
_CALL_ID = "gate-test-call"


def _call(tool_call_id: str = _CALL_ID):
    from zrb.llm.agent.types import ToolCallPart

    return ToolCallPart(
        tool_name="Shell", args={"command": "ls"}, tool_call_id=tool_call_id
    )


def _knobs(monkeypatch, *, judge: bool, auto_approve: bool = False):
    monkeypatch.setattr(CFG, "LLM_SHELL_JUDGE_ENABLED", judge, raising=False)
    monkeypatch.setattr(
        CFG, "LLM_SHELL_JUDGE_AUTO_APPROVE_ENABLED", auto_approve, raising=False
    )


def _judging(verdict: ShellVerdict):
    return patch(
        "zrb.llm.agent.run.deferred_calls.judge_or_unknown",
        AsyncMock(return_value=verdict),
    )


def _shell_args(sandbox_off: bool = False) -> dict[str, object]:
    args: dict[str, object] = {"command": "ls"}
    if sandbox_off:
        args["dangerously_skip_sandbox"] = True
    return args


def _is_shell(value: bool = True, sandbox_off: bool = False):
    return patch(
        "zrb.llm.agent.run.deferred_calls.shell_command_args",
        MagicMock(return_value=_shell_args(sandbox_off) if value else None),
    )


@pytest.fixture(autouse=True)
def _release_call():
    discard_judge_note(_CALL_ID)
    yield
    discard_judge_note(_CALL_ID)


@pytest.mark.asyncio
async def test_the_knob_being_off_means_no_call_and_no_line(monkeypatch):
    _knobs(monkeypatch, judge=False)
    with _judging(ShellVerdict(JUDGE_SAFE, "read-only")) as judge, _is_shell():
        verdict = await _apply_shell_judge(_call(), None, False)
    assert verdict is None
    judge.assert_not_called()
    assert read_judge_note(_CALL_ID) is None


@pytest.mark.asyncio
async def test_a_tool_that_is_not_a_shell_command_is_not_judged(monkeypatch):
    _knobs(monkeypatch, judge=True, auto_approve=True)
    with _judging(ShellVerdict(JUDGE_SAFE, "read-only")) as judge, _is_shell(False):
        verdict = await _apply_shell_judge(_call(), None, False)
    assert verdict is None
    judge.assert_not_called()


@pytest.mark.asyncio
async def test_an_enabled_judge_alone_only_annotates_the_prompt(monkeypatch):
    _knobs(monkeypatch, judge=True, auto_approve=False)
    with _judging(ShellVerdict(JUDGE_SAFE, "rebuilds build/ from source")), _is_shell():
        verdict = await _apply_shell_judge(_call(), None, False)
    assert verdict is None
    assert read_judge_note(_CALL_ID) == (JUDGE_SAFE, "rebuilds build/ from source")
    assert format_judge_line(_CALL_ID) == (
        "       judged safe: rebuilds build/ from source\n"
    )


@pytest.mark.asyncio
async def test_a_safe_verdict_is_approved_when_the_second_knob_is_on(monkeypatch):
    _knobs(monkeypatch, judge=True, auto_approve=True)
    with _judging(ShellVerdict(JUDGE_SAFE, "read-only listing")), _is_shell():
        verdict = await _apply_shell_judge(_call(), None, False)
    assert verdict is not None
    assert read_judge_note(_CALL_ID) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("level", [JUDGE_CAUTION, JUDGE_DANGEROUS, JUDGE_UNKNOWN])
async def test_only_a_safe_verdict_may_skip_the_prompt(monkeypatch, level):
    """Caution, danger and a judge that failed all still ask."""
    _knobs(monkeypatch, judge=True, auto_approve=True)
    with _judging(ShellVerdict(level, "something to weigh")), _is_shell():
        verdict = await _apply_shell_judge(_call(), None, False)
    assert verdict is None
    assert read_judge_note(_CALL_ID) == (level, "something to weigh")


@pytest.mark.asyncio
async def test_a_rule_that_says_ask_outranks_the_judge(monkeypatch):
    _knobs(monkeypatch, judge=True, auto_approve=True)
    with _judging(ShellVerdict(JUDGE_SAFE, "read-only")), _is_shell():
        verdict = await _apply_shell_judge(_call(), ASK, False)
    assert verdict is None
    assert read_judge_note(_CALL_ID) is not None


@pytest.mark.asyncio
async def test_a_hook_that_forces_the_prompt_outranks_the_judge(monkeypatch):
    _knobs(monkeypatch, judge=True, auto_approve=True)
    with _judging(ShellVerdict(JUDGE_SAFE, "read-only")), _is_shell():
        verdict = await _apply_shell_judge(_call(), ALLOW, True)
    assert verdict is None
    assert read_judge_note(_CALL_ID) is not None


@pytest.mark.asyncio
async def test_a_sandbox_escape_is_never_auto_approved(monkeypatch):
    """`ls /etc` with `dangerously_skip_sandbox` is not "safe": every other path
    in the cascade leaves a request to leave the sandbox for a human."""
    _knobs(monkeypatch, judge=True, auto_approve=True)
    with (
        _judging(ShellVerdict(JUDGE_SAFE, "read-only listing")),
        _is_shell(sandbox_off=True),
    ):
        verdict = await _apply_shell_judge(_call(), None, False)
    assert verdict is None
    assert read_judge_note(_CALL_ID) is not None


@pytest.mark.asyncio
async def test_the_judge_is_told_the_sandbox_is_off_for_such_a_call(monkeypatch):
    _knobs(monkeypatch, judge=True, auto_approve=False)
    seen: dict[str, object] = {}

    async def _judge(command: str, **kwargs: object) -> ShellVerdict:
        seen.update(kwargs)
        return ShellVerdict(JUDGE_CAUTION, "leaves the sandbox")

    with (
        patch("zrb.llm.agent.run.deferred_calls.judge_or_unknown", _judge),
        _is_shell(sandbox_off=True),
    ):
        await _apply_shell_judge(_call(), None, False)
    assert seen["sandbox_off"] is True


@pytest.mark.asyncio
async def test_a_cancelled_approval_does_not_leave_the_line_behind(monkeypatch):
    """The registry is process-global: a turn cancelled while the prompt waited
    must not keep the note for the rest of the run."""
    from types import SimpleNamespace

    from pydantic_ai import DeferredToolRequests

    from zrb.llm.agent.run import deferred_calls
    from zrb.llm.tool_call.judge_note import record_judge_note

    async def _cancel(*args, **kwargs):
        record_judge_note(_CALL_ID, JUDGE_CAUTION, "why it would matter")
        raise asyncio.CancelledError()

    with (
        patch.object(
            deferred_calls,
            "_apply_pre_tool_use_hook",
            AsyncMock(
                return_value=SimpleNamespace(
                    deny=False, allow=False, force_prompt=False, updated_input=None
                )
            ),
        ),
        patch.object(deferred_calls, "_resolve_approval", _cancel),
    ):
        with pytest.raises(asyncio.CancelledError):
            await deferred_calls.process_deferred_requests(
                DeferredToolRequests(approvals=[_call()]),
                None,
                MagicMock(),
                MagicMock(),
            )
    assert read_judge_note(_CALL_ID) is None


@pytest.mark.asyncio
async def test_the_judge_is_the_last_stage_before_the_prompt(monkeypatch):
    """Whatever the judge decides, the channel is not asked until it has."""
    _knobs(monkeypatch, judge=True, auto_approve=True)
    channel = MagicMock()
    channel.request_approval = AsyncMock()
    with (
        _judging(ShellVerdict(JUDGE_SAFE, "read-only")),
        _is_shell(),
        patch(
            "zrb.llm.agent.run.deferred_calls.get_interactive_mode", return_value=True
        ),
        patch("zrb.llm.shared.agent_state.get_current_yolo", return_value=False),
    ):
        verdict = await _resolve_approval(
            _call(), MagicMock(), None, channel, None, force_ask=False
        )
    assert verdict is not None
    channel.request_approval.assert_not_called()


def _hook_manager() -> MagicMock:
    manager = MagicMock()
    manager.execute_hooks = AsyncMock(return_value=[])
    return manager


def _hook_events(manager: MagicMock) -> list:
    return [c.args[0] for c in manager.execute_hooks.call_args_list]


@pytest.mark.asyncio
async def test_the_hook_is_not_told_about_a_prompt_the_judge_skips(monkeypatch):
    """Go's report: with auto-approve on, the approval was still announced aloud.

    The speech feature listens on `PermissionRequest` and reads the question
    out, so a hook that fires for a prompt the judge removed makes a person
    hear a question nobody is waiting to have answered. The event's own
    contract is "now that the call will prompt".
    """
    from zrb.llm.hook.contracts.types import HookEvent

    _knobs(monkeypatch, judge=True, auto_approve=True)
    hook_manager = _hook_manager()
    with (
        _judging(ShellVerdict(JUDGE_SAFE, "read-only")),
        _is_shell(),
        patch(
            "zrb.llm.agent.run.deferred_calls.get_interactive_mode", return_value=True
        ),
        patch("zrb.llm.shared.agent_state.get_current_yolo", return_value=False),
    ):
        verdict = await _resolve_approval(
            _call(), MagicMock(), None, None, hook_manager, force_ask=False
        )
    assert verdict is not None
    assert HookEvent.PERMISSION_REQUEST not in _hook_events(hook_manager)


@pytest.mark.asyncio
async def test_the_hook_hears_about_a_prompt_that_will_happen(monkeypatch):
    """The other half of the same rule: a prompt that does happen is announced."""
    from zrb.llm.hook.contracts.types import HookEvent

    _knobs(monkeypatch, judge=True, auto_approve=False)
    hook_manager = _hook_manager()
    channel = MagicMock()
    channel.request_approval = AsyncMock(return_value=MagicMock(approved=True))
    with (
        _judging(ShellVerdict(JUDGE_SAFE, "read-only")),
        _is_shell(),
        patch(
            "zrb.llm.agent.run.deferred_calls.get_interactive_mode", return_value=True
        ),
        patch("zrb.llm.shared.agent_state.get_current_yolo", return_value=False),
    ):
        await _resolve_approval(
            _call(), MagicMock(), None, channel, hook_manager, force_ask=False
        )
    assert HookEvent.PERMISSION_REQUEST in _hook_events(hook_manager)
    assert read_judge_note(_CALL_ID) is not None
