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
    """Existing session names matching `arg_prefix`.

    A delegated sub-agent transcript (see `subagent_session_naming.py`) is labeled
    "Sub-agent: <name>" rather than the generic "Session Name" — otherwise
    it's indistinguishable from an ordinary saved session in the completion
    dropdown, and there is no other discovery mechanism in the CLI TUI for
    "what sub-agent sessions exist"; this label is it.
    """
    # lazy: zrb internal — this module is cheap and dependency-free, but
    # even a cheap import isn't worth paying on the completion hot path
    # (hit on every keystroke) unless /load is actually being typed.
    from zrb.llm.util.subagent_session_naming import parse_delegated_session

    for res in history_manager.search(arg_prefix)[:10]:
        delegated = parse_delegated_session(res)
        display_meta = (
            f"Sub-agent: {delegated[1]}" if delegated is not None else "Session Name"
        )
        yield Completion(
            res,
            start_position=-len(arg_prefix),
            display_meta=display_meta,
        )


def complete_photo_arg(arg_prefix: str) -> Iterable[Completion]:
    """Camera device ids/names for `/photo <device>` (best-effort, cached)."""
    # lazy: tests patch zrb.llm.util.camera.list_camera_devices /
    # maybe_refresh_camera_devices; hoisting would bind the names at this
    # module's load time and bypass the mocks.
    from zrb.llm.util.camera import list_camera_devices, maybe_refresh_camera_devices

    # Windows dshow names need a subprocess probe; schedule it as a
    # fire-and-forget task so no keystroke ever blocks on ffmpeg.
    maybe_refresh_camera_devices()
    for device in list_camera_devices():
        if device.startswith(arg_prefix):
            yield Completion(
                device,
                start_position=-len(arg_prefix),
                display_meta="Camera Device",
            )


def complete_redirect_arg(arg_prefix: str) -> Iterable[Completion]:
    """A single response-<timestamp>.txt suggestion for redirecting output."""
    ts = datetime.now().strftime("response-%Y-%m-%d-%H-%M.txt")
    if ts.startswith(arg_prefix):
        yield Completion(
            ts,
            start_position=-len(arg_prefix),
            display_meta="File Name",
        )


def complete_copy_arg(arg_prefix: str) -> Iterable[Completion]:
    """A single transcript-<timestamp>.txt suggestion for copying transcript."""
    ts = datetime.now().strftime("transcript-%Y-%m-%d-%H-%M.txt")
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
