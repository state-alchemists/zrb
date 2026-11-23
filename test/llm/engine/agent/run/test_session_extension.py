"""Tests for turn-end (STOP) hook extension semantics."""

from zrb.llm.capabilities.hook.execution.executor import HookExecutionResult
from zrb.llm.engine.agent.run.session_extension import (
    STOP_HOOK_BLOCK_CAP,
    STOP_HOOK_SYSTEM_MESSAGE_CAP,
    ExtensionState,
    apply_turn_end_extension,
    resolve_extended_return,
)


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


def test_a_side_effect_extension_after_a_block_returns_the_continuation():
    """block -> continuation -> systemMessage(replace_response=False).

    The continuation the block asked for is the answer. The side-effect
    extension used to overwrite `return_extended` while the pre-continuation
    pair stayed in `original_*`, so the final return resurrected the answer
    from before the continuation.
    """
    state = ExtensionState()
    pre_continuation_history = ["pre-continuation message"]
    continuation_history = ["continuation message"]

    block = apply_turn_end_extension(
        [HookExecutionResult(success=True, decision="block", reason="keep going")],
        state,
        "pre-continuation answer",
        pre_continuation_history,
        _noop,
    )
    assert block.should_continue is True

    side_effect = apply_turn_end_extension(
        [HookExecutionResult(success=True, system_message="record the decision")],
        state,
        "continuation answer",
        continuation_history,
        _noop,
    )
    assert side_effect.should_continue is True

    output, history = resolve_extended_return(
        state, "side-effect acknowledgment", ["side-effect message"]
    )

    assert output == "continuation answer"
    assert output != "pre-continuation answer"
    assert history is continuation_history
    assert history is not pre_continuation_history


def test_without_an_extension_the_current_pair_is_returned():
    output, history = resolve_extended_return(ExtensionState(), "answer", ["message"])
    assert output == "answer"
    assert history == ["message"]


def test_a_replacing_extension_returns_the_current_pair():
    """replace_response=True keeps returning the extended turn's own pair."""
    state = ExtensionState()
    apply_turn_end_extension(
        [
            HookExecutionResult(
                success=True, system_message="summarize", replace_response=True
            )
        ],
        state,
        "original answer",
        ["original message"],
        _noop,
    )

    output, history = resolve_extended_return(state, "summary", ["summary message"])

    assert output == "summary"
    assert history == ["summary message"]
