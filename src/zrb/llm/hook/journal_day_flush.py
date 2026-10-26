"""The built-in day flush: what a compaction is about to replace is written
into the journal's day tier first.

Registered on every `HookManager` whenever `LLM_JOURNAL_ENABLED` is on, so a
journaled setup gets a day record without configuring anything — the same
posture as the built-in journal-compliance judge.

Deliberately dumb. A flush rides on the compaction that is already the most
expensive moment of a session, so it takes no model call and makes no judgement
about what mattered: one line saying which span is going away, how big it was,
and the last thing the user asked. A model-driven "keep the five lines worth
keeping" pass belongs in a slower hook, if it ever belongs anywhere.

A failure here must never block compaction: the writer catches its own errors
and the hook always returns a result with no output.
"""

import os
from datetime import datetime
from typing import TYPE_CHECKING

from zrb.config.config import CFG
from zrb.llm.hook.enablement import is_builtin_hook_enabled
from zrb.llm.hook.interface import HookResult
from zrb.llm.hook.types import HookEvent

if TYPE_CHECKING:
    from zrb.llm.hook.interface import HookContext
    from zrb.llm.hook.manager import HookManager

_NAME = "journal-day-flush"
DAY_DIR_NAME = "days"
"""Subdirectory of the journal holding `YYYY-MM-DD.md`, one file per day."""

QUOTE_LIMIT = 160
"""Characters of the last user turn kept in the flushed line."""

DEFAULT_IMPORTANCE = 2
"""A scaffold line, not a kept moment: the sweep may drop it without loss."""

AUTO_FLUSH_MARKER = "auto-flush"
_LIVE_CONTEXT_MARKER = "<live-context>"
_USER_KINDS = ("request", "user")


def _day_path(now: datetime, root: str | None = None) -> str:
    """The day file for *now* under the journal directory."""
    base = os.path.abspath(
        os.path.expanduser(root if root is not None else CFG.LLM_JOURNAL_DIR)
    )
    return os.path.join(base, DAY_DIR_NAME, f"{now.strftime('%Y-%m-%d')}.md")


def _is_user_turn(message: object) -> bool:
    """Whether *message* is a user turn, however it arrived (object or dict)."""
    if isinstance(message, dict):
        kind = message.get("role") or message.get("kind") or ""
        parts = message.get("parts") or []
    else:
        kind = getattr(message, "kind", "") or getattr(message, "role", "") or ""
        parts = getattr(message, "parts", None) or []
    if str(kind) in _USER_KINDS:
        return True
    for part in parts if isinstance(parts, list) else []:
        if isinstance(part, dict):
            part_kind = part.get("part_kind")
        else:
            part_kind = getattr(part, "part_kind", None)
        if str(part_kind or "").startswith("user"):
            return True
    return False


def _words(value: object) -> str:
    """Every word *value* carries, and nothing else.

    A prompt, a user part or a message may hold a string, or a list mixing that
    text with attachments. Attachments are skipped rather than stringified: the
    `str` of an image part carries the repr of its bytes, which is nobody's words
    and would land in the journal as though it were. The same shape arrives as a
    `ModelRequest` with a list in its user part, as a JSON replay of one, and as
    the flat list a prompt becomes when it carries an attachment.
    """
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        return " ".join(_words(item) for item in value)
    if isinstance(value, dict):
        return _words(value.get("parts") or value.get("content"))
    parts = getattr(value, "parts", None)
    if isinstance(parts, (list, tuple)):
        return _words(list(parts))
    content = getattr(value, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, (list, tuple, dict)):
        return _words(content)
    return ""


def _typed_text(message: object) -> str:
    """The words the user typed in one turn, clipped; `""` when there are none.

    The live-context block rides inside the turn, so only the text above it is
    quoted: that is the part the user actually typed.
    """
    return " ".join(_words(message).split()).split(_LIVE_CONTEXT_MARKER)[0].strip()[
        :QUOTE_LIMIT
    ]


def _last_user_ask(data: dict[str, object]) -> str:
    """What the user last asked: this turn's prompt, else the newest turn in history.

    `_prepare_history` fires PRE_COMPACT *before* the prompt joins the history, so
    `prompt` is the only place the ask that caused this compaction can come from.
    History is what a compaction nothing asked for has to offer.
    """
    prompt = data.get("prompt")
    if prompt is not None:
        asked = _typed_text(prompt)
        if asked:
            return asked
    history = data.get("history")
    for message in reversed(history if isinstance(history, list) else []):
        if not _is_user_turn(message):
            continue
        asked = _typed_text(message)
        if asked:
            return asked
    return ""


def format_day_line(now: datetime, data: dict[str, object], cwd: str = "") -> str:
    """The one line a flush appends: when, where, how much, and what was asked."""
    facts: list[str] = []
    count = data.get("message_count")
    tokens = data.get("token_count")
    if isinstance(count, int):
        facts.append(f"{count} messages")
    if isinstance(tokens, int):
        facts.append(f"~{tokens // 1000}k tokens" if tokens >= 1000 else f"{tokens} tokens")
    where = " ".join(str(cwd or data.get("cwd") or "").split()) or "?"
    ask = _last_user_ask(data)
    quote = f' · last ask: "{ask}"' if ask else ""
    return (
        f"- {now.strftime('%H:%M')} · {where} · compaction replaced "
        f"{', '.join(facts) or 'a span'}; no hand-written line existed for it"
        f"{quote} · imp {DEFAULT_IMPORTANCE} · {AUTO_FLUSH_MARKER}"
    )


def _create_day_file(path: str, moment: datetime) -> None:
    """Create the day file with its heading, unless something else got there first.

    ``"x"`` is one atomic create-or-fail, so two sessions compacting into the same
    new day cannot both open it for writing. An existence check followed by ``"w"``
    could: both would see no file, and the second would truncate the record the
    first had already written. ``FileExistsError`` is caught here rather than by
    the caller, which must go on to append.
    """
    try:
        with open(path, "x", encoding="utf-8") as f:
            f.write(f"# {moment.strftime('%Y-%m-%d (%a)')}\n\n")
    except FileExistsError:
        pass  # another session owns the heading; the line below is still ours to add


def append_day_line(
    line: str, now: datetime | None = None, root: str | None = None
) -> "str | None":
    """Append *line* to the day file, creating the file with its heading.

    Returns the path written, or ``None`` when the write failed — the caller
    treats that as "no flush", never as an error to report upward.
    """
    moment = now or datetime.now()
    path = _day_path(moment, root)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        _create_day_file(path, moment)
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError as e:
        CFG.LOGGER.debug(f"journal day flush could not write {path}: {e}")
        return None
    return path


class _DayFlush:
    """The flush, as a callable that answers to the name both knobs use.

    `HookRegistry._hook_name` reads a config's name, then the hook's `__name__`,
    then its `name`. A plain function would answer with its Python name,
    `journal_day_flush`, which `LLM_HOOKS=journal-day-flush` does not match — an
    allowlist naming the flush would have dropped it in silence. An object has no
    `__name__`, so the documented name is the one that answers.
    """

    name = _NAME

    async def __call__(self, context: "HookContext") -> HookResult:
        """The PreCompact hook: record the span before it is replaced."""
        data = context.event_data if isinstance(context.event_data, dict) else {}
        line = format_day_line(datetime.now(), data, cwd=context.cwd or "")
        append_day_line(line)
        return HookResult()


journal_day_flush = _DayFlush()
"""The one flush hook; see `_DayFlush` for why it is an object rather than a function."""


def register_journal_day_flush_hook(manager: "HookManager") -> None:
    """Hook factory: register the flush unless journaling is off, or the hook is
    named in `LLM_HOOKS_DISABLED`."""
    if not CFG.LLM_JOURNAL_ENABLED or not is_builtin_hook_enabled(_NAME):
        return
    manager.add_hook(journal_day_flush, events=[HookEvent.PRE_COMPACT])
