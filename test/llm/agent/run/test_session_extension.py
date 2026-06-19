"""Tests for turn-end (STOP) hook extension semantics."""

from zrb.llm.agent.run.session_extension import (
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
