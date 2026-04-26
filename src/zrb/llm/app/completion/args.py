"""Per-command argument completers used by `InputCompleter._get_argument_completions`.

Each function yields `prompt_toolkit` `Completion` objects for one slash
command's argument. Stateless — caches and history-manager handles are
passed in by the caller.
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable

from prompt_toolkit.completion import Completion

from zrb.llm.history_manager.any_history_manager import AnyHistoryManager


def complete_save_arg(
    arg_prefix: str,
    history_manager: AnyHistoryManager,
) -> Iterable[Completion]:
    """Existing session names plus a timestamp default for new saves."""
    results = history_manager.search(arg_prefix)
    for res in results[:10]:
        yield Completion(
            res,
            start_position=-len(arg_prefix),
            display_meta="Existing Session",
        )

    ts = datetime.now().strftime("%Y-%m-%d-%H-%M")
    if ts.startswith(arg_prefix):
        yield Completion(
            ts,
            start_position=-len(arg_prefix),
            display_meta="New Session",
        )


def complete_load_arg(
    arg_prefix: str,
    history_manager: AnyHistoryManager,
) -> Iterable[Completion]:
    """Existing session names matching `arg_prefix`."""
    for res in history_manager.search(arg_prefix)[:10]:
        yield Completion(
            res,
            start_position=-len(arg_prefix),
            display_meta="Session Name",
        )


def complete_redirect_arg(arg_prefix: str) -> Iterable[Completion]:
    """A single timestamp.txt suggestion for redirecting last response to file."""
    ts = datetime.now().strftime("%Y-%m-%d-%H-%M.txt")
    if ts.startswith(arg_prefix):
        yield Completion(
            ts,
            start_position=-len(arg_prefix),
            display_meta="File Name",
        )


def complete_exec_arg(
    arg_prefix: str,
    cmd_history: list[str],
) -> Iterable[Completion]:
    """Shell-history matches for `!exec` (most recent first)."""
    matches = [h for h in cmd_history if h.startswith(arg_prefix)]
    for h in reversed(matches):
        yield Completion(
            h,
            start_position=-len(arg_prefix),
            display_meta="Shell Command",
        )
