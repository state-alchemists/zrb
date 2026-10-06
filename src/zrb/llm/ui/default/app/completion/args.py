"""Per-command argument completers used by `InputCompleter._get_argument_completions`.

Each function yields `prompt_toolkit` `Completion` objects for one slash
command's argument. Stateless — caches and history-manager handles are
passed in by the caller.
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable

from prompt_toolkit.completion import Completion

from zrb.config.config import CFG
from zrb.llm.history_manager.any_history_manager import AnyHistoryManager

# `/set` names that switch the UI's live model slots rather than a CFG field.
_LIVE_MODEL_SLOTS = frozenset({"model", "small_model", "multimodal_model"})
# Names (CFG fields or live model slots) whose value completion offers known
# model names. Normalized to uppercase so the case-insensitive `/set` name
# lookup works for lowercase-typed names too.
_MODEL_SETTINGS = frozenset(
    {"LLM_MODEL", "LLM_SMALL_MODEL", "LLM_MULTIMODAL_MODEL"}
    | {slot.upper() for slot in _LIVE_MODEL_SLOTS}
)


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
    """Existing sessions matching `arg_prefix`, labeling delegated sessions."""
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


def complete_set_name_arg(arg_prefix: str) -> Iterable[Completion]:
    """Settable CFG field names, plus the three live model slots.

    Case-insensitive prefix match, since CFG names are uppercase but a user
    may type them lowercase.
    """
    lower = arg_prefix.lower()
    for slot in sorted(_LIVE_MODEL_SLOTS):
        if slot.lower().startswith(lower):
            yield Completion(
                slot, start_position=-len(arg_prefix), display_meta="Live model slot"
            )
    for name in CFG.get_settable_field_names():
        if name.lower().startswith(lower):
            yield Completion(
                name, start_position=-len(arg_prefix), display_meta="Config setting"
            )


def complete_set_value_arg(
    name: str, arg_prefix: str, model_names: list[str]
) -> Iterable[Completion]:
    """Value hints for `CFG.<name>`: known models, on/off for bools, current value."""
    normalized_name = name.upper()
    if normalized_name in _MODEL_SETTINGS:
        yield from _prefix_completions(arg_prefix, model_names, "Model Name")

    field = CFG.get_settable_field(normalized_name)
    if field is not None and field.is_boolean:
        yield from _prefix_completions(arg_prefix, ["on", "off"], "Boolean")

    if field is None or not field.secret:
        try:
            current = getattr(CFG, normalized_name, None)
        except (ValueError, TypeError):
            # A value in the environment this field cannot read (e.g. an int
            # setting holding "abc") has no current value to offer.
            current = None
        if current is not None and str(current) != "":
            shown = _display_value(field, current)
            if shown.lower().startswith(arg_prefix.lower()):
                yield Completion(
                    shown,
                    start_position=-len(arg_prefix),
                    display_meta="Current value",
                )


def _prefix_completions(
    prefix: str, values: Iterable[str], meta: str
) -> Iterable[Completion]:
    lower = prefix.lower()
    for value in values:
        if value.lower().startswith(lower):
            yield Completion(value, start_position=-len(prefix), display_meta=meta)


def _display_value(field, current) -> str:
    """Render a CFG field's current value the way a user would type it.

    Non-boolean values go through the field's own serializer, so the offered
    text is exactly what the matching cast reads back; `str(current)` would
    render a list as ``['/set']``, which parses back as one bracketed entry.
    """
    if field is not None and field.is_boolean:
        return "on" if current else "off"
    if field is None:
        return str(current)
    serialized = field.serialize(current)
    return serialized if isinstance(serialized, str) else str(current)
