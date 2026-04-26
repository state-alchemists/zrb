"""SESSION_END hook extension semantics for `run_agent`.

A SESSION_END hook may return a `systemMessage` to extend the conversation
(e.g. journaling that wants the LLM to summarize and stash). The
`replace_response` flag controls whether the extended response replaces
the user-facing return or whether the original (pre-extension) response
is preserved and the extension runs purely for side effects.

If multiple extensions occur, the *last* `replace_response` wins; the
*first* original output/history is preserved as the candidate to return.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from zrb.config.config import CFG
from zrb.llm.agent.run.hook_result_extractor import (
    extract_replace_response,
    extract_system_message,
)


@dataclass
class ExtensionState:
    """Tracks whether the session was extended and what to return."""

    extended: bool = False
    return_extended: bool = False
    original_output: Any = None
    original_history: list[Any] | None = None


@dataclass
class ExtensionOutcome:
    """Result of evaluating SESSION_END hook results.

    `should_continue=True` means the loop should iterate again with
    `(new_message, new_history)` as the next user prompt + history.
    """

    should_continue: bool
    new_message: Any = None
    new_history: list[Any] | None = None


def apply_session_end_extension(
    session_end_results: list[Any],
    state: ExtensionState,
    result_output: Any,
    run_history: list[Any],
    print_fn: Callable[[str], Any],
) -> ExtensionOutcome:
    """Inspect SESSION_END hook results and decide whether to extend the session."""
    session_end_message = extract_system_message(session_end_results)
    if not session_end_message:
        return ExtensionOutcome(should_continue=False)

    replace_response = extract_replace_response(session_end_results)
    CFG.LOGGER.debug(
        f"SESSION_END hook returned systemMessage, continuing session: "
        f"{session_end_message[:100]}..."
    )
    CFG.LOGGER.debug(f"SESSION_END hook replace_response={replace_response}")

    # Capture original BEFORE the first extension so we can restore later.
    if not state.extended:
        state.original_output = result_output
        state.original_history = run_history

    # Last extension wins for the replace flag.
    state.extended = True
    state.return_extended = replace_response

    print_fn(f"\n[SYSTEM] {session_end_message}\n")
    return ExtensionOutcome(
        should_continue=True,
        new_message=session_end_message,
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
