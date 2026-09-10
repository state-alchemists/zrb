"""Tests for turn-end (STOP) hook extension semantics."""

from zrb.llm.agent.run.session_extension import (
    STOP_HOOK_BLOCK_CAP,
    STOP_HOOK_SYSTEM_MESSAGE_CAP,
    ExtensionState,
    apply_turn_end_extension,
)
from zrb.llm.hook.executor import HookExecutionResult


def _noop(msg):
    """A print_fn stub that swallows its argument."""


def test_clean_stop_does_not_extend():
    """No block, systemMessage, or continue signal → the turn ends."""
    outcome = apply_turn_end_extension(
        [HookExecutionResult(success=True)], ExtensionState(), "out", [], _noop
    )
    assert outcome.should_continue is False


def test_block_extends_turn():
    """A Stop hook decision=block re-runs the turn (block-to-continue)."""
    results = [HookExecutionResult(success=True, decision="block", reason="keep going")]
    outcome = apply_turn_end_extension(results, ExtensionState(), "out", [], _noop)
    assert outcome.should_continue is True
    assert outcome.new_message == "keep going"


def test_continue_false_halts():
    """A Stop hook continue=false ends the run."""
    results = [
        HookExecutionResult(
            success=True, continue_execution=False, data={"stopReason": "done"}
        )
    ]
    outcome = apply_turn_end_extension(results, ExtensionState(), "out", [], _noop)
    assert outcome.should_continue is False


def test_continue_false_overrides_block_to_continue():
    """continue=false is unconditional: it wins even when the same batch also
    carries a block-to-continue, so the agent is not re-run."""
    results = [
        HookExecutionResult(
            success=True,
            decision="block",
            reason="re-run",
            continue_execution=False,
        )
    ]
    outcome = apply_turn_end_extension(results, ExtensionState(), "out", [], _noop)
    assert outcome.should_continue is False


def test_system_message_extends_turn():
    """A Stop hook returning a systemMessage re-runs the turn once."""
    results = [HookExecutionResult(success=True, system_message="journal your work")]
    state = ExtensionState()
    outcome = apply_turn_end_extension(results, state, "out", [], _noop)
    assert outcome.should_continue is True
    assert outcome.new_message == "journal your work"
    assert state.system_message_count == 1


def test_system_message_extension_is_capped():
    """A hook that returns a systemMessage every turn cannot loop forever."""
    results = [HookExecutionResult(success=True, system_message="again")]
    state = ExtensionState()
    extensions = 0
    for _ in range(STOP_HOOK_SYSTEM_MESSAGE_CAP + 5):
        if not apply_turn_end_extension(
            results, state, "out", [], _noop
        ).should_continue:
            break
        extensions += 1
    assert extensions == STOP_HOOK_SYSTEM_MESSAGE_CAP


def test_block_and_system_message_caps_are_independent():
    """Exhausting one extension path does not consume the other's budget."""
    blocks = [HookExecutionResult(success=True, decision="block", reason="go")]
    messages = [HookExecutionResult(success=True, system_message="note")]
    state = ExtensionState()
    for _ in range(STOP_HOOK_BLOCK_CAP):
        apply_turn_end_extension(blocks, state, "out", [], _noop)
    assert (
        apply_turn_end_extension(blocks, state, "out", [], _noop).should_continue
        is False
    )
    assert (
        apply_turn_end_extension(messages, state, "out", [], _noop).should_continue
        is True
    )
