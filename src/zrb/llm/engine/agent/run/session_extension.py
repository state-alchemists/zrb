"""STOP-hook extension semantics for ``run_agent``.

Hooks can request a continuation by blocking or by returning ``systemMessage``;
caps prevent either path from looping indefinitely."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from zrb.config.config import CFG
from zrb.llm.engine.agent.run.hook_result_extractor import (
    extract_block_decision,
    extract_continue_decision,
    extract_replace_response,
    extract_system_message,
)

if TYPE_CHECKING:
    from zrb.llm.capabilities.hook.execution.executor import HookExecutionResult
    from zrb.llm.engine.agent.run.typing_aliases import History, PrintFn, PromptMessage

# Mirrors Claude Code's CLAUDE_CODE_STOP_HOOK_BLOCK_CAP: after this many
# consecutive Stop-hook blocks without the turn ending, allow the stop so a
# misbehaving hook can't loop the agent forever.
STOP_HOOK_BLOCK_CAP = 8
# The same backstop for the systemMessage extension. A hook that returns a
# systemMessage on every STOP re-runs the turn each time, so this path needs its
# own ceiling — a hook whose own once-per-turn guard misfires would otherwise
# loop the agent with no bound at all.
STOP_HOOK_SYSTEM_MESSAGE_CAP = 8


@dataclass
class ExtensionState:
    """Tracks whether the turn was extended and what to return."""

    extended: bool = False
    return_extended: bool = False
    # The pair to return when the latest extension did not replace the
    # response. `answer_captured` says whether it holds a frozen answer: a
    # `None` output is a legitimate answer for a nullable output type, so the
    # pair cannot use `None` as "not captured yet". A block clears both; a
    # replacing extension records its output; the first side-effect extension
    # freezes the pair and later side-effect extensions keep it. A second
    # side-effect run must not overwrite the answer with its own
    # acknowledgement.
    answer_output: Any = None
    answer_history: History | None = None
    answer_captured: bool = False
    block_count: int = 0
    system_message_count: int = 0


@dataclass
class ExtensionOutcome:
    """Result of evaluating STOP hook results.

    `should_continue=True` means the loop should iterate again with
    `(new_message, new_history)` as the next user prompt + history. `blocked`
    distinguishes a Claude block-to-continue from a systemMessage extension.
    """

    should_continue: bool
    new_message: PromptMessage = None
    new_history: History | None = None
    blocked: bool = False


def apply_turn_end_extension(
    stop_results: list[HookExecutionResult],
    state: ExtensionState,
    result_output: Any,
    run_history: History,
    print_fn: PrintFn,
) -> ExtensionOutcome:
    """Inspect STOP hook results and decide whether to extend the turn."""
    # 0. continue: false is an explicit "stop all processing" request. It is
    # unconditional and overrides any block-to-continue or systemMessage
    # extension below — the turn ends now and stopReason is shown to the user.
    cont = extract_continue_decision(stop_results)
    if cont.stop:
        if cont.reason:
            print_fn(f"\n[SYSTEM] {cont.reason}\n")
        return ExtensionOutcome(should_continue=False)

    # 1. Claude-style block-to-continue.
    block = extract_block_decision(stop_results)
    if block.blocked:
        if state.block_count >= STOP_HOOK_BLOCK_CAP:
            CFG.LOGGER.warning(
                "Stop hook blocked %d times in a row; allowing the turn to end.",
                STOP_HOOK_BLOCK_CAP,
            )
            return ExtensionOutcome(should_continue=False)
        message = block.reason or "Please continue."
        if block.additional_context:
            message = f"{message}\n\n{block.additional_context}"
        state.extended = True
        # The continuation is what the user asked the hook to force, so it is the
        # answer we return.
        state.return_extended = True
        # A block supersedes any answer frozen by an earlier extension; the
        # continuation that runs next is the answer if a side-effect extension
        # follows it.
        state.answer_output = None
        state.answer_history = None
        state.answer_captured = False
        state.block_count += 1
        print_fn(f"\n[SYSTEM] {message}\n")
        return ExtensionOutcome(
            should_continue=True,
            new_message=message,
            new_history=run_history,
            blocked=True,
        )

    # 2. systemMessage extension (memory review, summarization, ...).
    message = extract_system_message(stop_results)
    if not message:
        return ExtensionOutcome(should_continue=False)
    if state.system_message_count >= STOP_HOOK_SYSTEM_MESSAGE_CAP:
        CFG.LOGGER.warning(
            "Stop hook returned a systemMessage %d times in a row; allowing the "
            "turn to end.",
            STOP_HOOK_SYSTEM_MESSAGE_CAP,
        )
        return ExtensionOutcome(should_continue=False)
    state.system_message_count += 1

    replace_response = extract_replace_response(stop_results)
    CFG.LOGGER.debug(
        f"STOP hook returned systemMessage, continuing turn: {message[:100]}..."
    )
    CFG.LOGGER.debug(f"STOP hook replace_response={replace_response}")
    state.extended = True
    state.return_extended = replace_response
    if replace_response:
        # This hook runs before its continuation: `result_output` is the answer
        # the replacement supersedes, not the replacement. Clear any earlier
        # freeze; the first side-effect extension after the continuation will
        # freeze that continuation's result.
        state.answer_output = None
        state.answer_history = None
        state.answer_captured = False
    elif not state.answer_captured:
        # The first side-effect run freezes the answer it was asked to leave
        # alone — `None` included, since a nullable output can legitimately be
        # `None`. Later side-effect runs must not refresh it: doing so would
        # replace the answer with the previous side-effect acknowledgement.
        state.answer_output = result_output
        state.answer_history = run_history
        state.answer_captured = True
    print_fn(f"\n[SYSTEM] {message}\n")
    return ExtensionOutcome(
        should_continue=True,
        new_message=message,
        new_history=run_history,
    )


def resolve_extended_return(
    state: ExtensionState,
    result_output: Any,
    run_history: History,
) -> tuple[Any, History]:
    """Pick (output, history) to return based on the last extension.

    No extension returns the current pair. A replacing extension (a block or
    `replace_response=True`) returns it too. A non-replacing extension returns
    the pair frozen when it started, so a continuation accepted before it is
    not discarded; a frozen `None` is a real output and is returned as such.
    """
    if not state.extended:
        return result_output, run_history
    if state.return_extended:
        CFG.LOGGER.debug("Returning extended response (replace_response=True)")
        return result_output, run_history
    CFG.LOGGER.debug("Returning frozen response (replace_response=False)")
    return state.answer_output, state.answer_history or []
