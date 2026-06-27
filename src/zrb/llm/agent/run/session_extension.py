"""Turn-end (STOP) hook extension semantics for `run_agent`.

When an agent turn completes, the STOP hook fires. A hook may extend the turn in
one of two Claude-compatible ways:

* **Block-to-continue** — a hook returns ``decision: "block"`` with a ``reason``
  (optionally ``additionalContext``). The agent runs another turn with that text
  injected as the next prompt, and the continued response becomes the answer. A
  consecutive-block cap stops a hook that would block forever.
* **systemMessage extension** — a hook returns a ``systemMessage`` (e.g. the
  journaling reminder). The agent runs one more turn; ``replaceResponse`` controls
  whether the continued response or the original is returned to the user.

If multiple extensions occur, the *last* ``replace_response`` wins; the *first*
original output/history is preserved as the candidate to return.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from zrb.config.config import CFG
from zrb.llm.agent.run.hook_result_extractor import (
    extract_block_decision,
    extract_continue_decision,
    extract_replace_response,
    extract_system_message,
)

# Mirrors Claude Code's CLAUDE_CODE_STOP_HOOK_BLOCK_CAP: after this many
# consecutive Stop-hook blocks without the turn ending, allow the stop so a
# misbehaving hook can't loop the agent forever.
STOP_HOOK_BLOCK_CAP = 8


@dataclass
class ExtensionState:
    """Tracks whether the turn was extended and what to return."""

    extended: bool = False
    return_extended: bool = False
    original_output: Any = None
    original_history: list[Any] | None = None
    block_count: int = 0


@dataclass
class ExtensionOutcome:
    """Result of evaluating STOP hook results.

    `should_continue=True` means the loop should iterate again with
    `(new_message, new_history)` as the next user prompt + history. `blocked`
    distinguishes a Claude block-to-continue from a systemMessage extension.
    """

    should_continue: bool
    new_message: Any = None
    new_history: list[Any] | None = None
    blocked: bool = False


def _capture_original(
    state: ExtensionState, result_output: Any, run_history: list[Any]
) -> None:
    """Snapshot the pre-extension output/history before the first extension."""
    if not state.extended:
        state.original_output = result_output
        state.original_history = run_history


def apply_turn_end_extension(
    stop_results: list[Any],
    state: ExtensionState,
    result_output: Any,
    run_history: list[Any],
    print_fn: Callable[[str], Any],
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
        _capture_original(state, result_output, run_history)
        state.extended = True
        # The continuation is what the user asked the hook to force, so it is the
        # answer we return.
        state.return_extended = True
        state.block_count += 1
        print_fn(f"\n[SYSTEM] {message}\n")
        return ExtensionOutcome(
            should_continue=True,
            new_message=message,
            new_history=run_history,
            blocked=True,
        )

    # 2. systemMessage extension (journaling, summarization, ...).
    message = extract_system_message(stop_results)
    if not message:
        return ExtensionOutcome(should_continue=False)

    replace_response = extract_replace_response(stop_results)
    CFG.LOGGER.debug(
        f"STOP hook returned systemMessage, continuing turn: {message[:100]}..."
    )
    CFG.LOGGER.debug(f"STOP hook replace_response={replace_response}")
    _capture_original(state, result_output, run_history)
    state.extended = True
    state.return_extended = replace_response
    print_fn(f"\n[SYSTEM] {message}\n")
    return ExtensionOutcome(
        should_continue=True,
        new_message=message,
        new_history=run_history,
    )


def resolve_extended_return(
    state: ExtensionState,
    result_output: Any,
    run_history: list[Any],
) -> tuple[Any, list[Any]]:
    """Pick (output, history) to return based on the last `replace_response`."""
    if not state.extended:
        return result_output, run_history
    if state.return_extended:
        CFG.LOGGER.debug("Returning extended response (replace_response=True)")
        return result_output, run_history
    CFG.LOGGER.debug("Returning original response (replace_response=False)")
    return state.original_output, state.original_history or []
