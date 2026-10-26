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
from typing import TYPE_CHECKING, Any

from zrb.config.config import CFG
from zrb.llm.hook.enablement import is_builtin_hook_enabled
from zrb.llm.hook.interface import HookResult
from zrb.llm.hook.types import HookEvent
from zrb.llm.message_text import message_content_text

if TYPE_CHECKING:
    from zrb.llm.hook.interface import HookCallable, HookContext
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


def _is_user_turn(message: Any) -> bool:
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


def _message_text(message: Any) -> str:
    """One message's text, from a live `ModelRequest` or from a JSON dict.

    `message_content_text` is the authority for the objects the runner hands
    over; a replay written as JSON has no such type, so its parts are read here.
    """
    if not isinstance(message, dict):
        return message_content_text(message)
    parts = message.get("parts") or message.get("content") or []
    if isinstance(parts, str):
        return parts
    if isinstance(parts, dict):
        parts = [parts]
    chunks = [
        str(part.get("content") or "") if isinstance(part, dict) else str(part)
        for part in (parts if isinstance(parts, list) else [])
    ]
    return " ".join(chunks)


def _last_user_ask(history: Any) -> str:
    """The newest user turn's text, clipped; `""` when there is none.

    The live-context block rides inside that turn, so only the text above it is
    quoted: that is the part the user actually typed.
    """
    for message in reversed(history if isinstance(history, list) else []):
        if not _is_user_turn(message):
            continue
        text = " ".join(_message_text(message).split())
        head = text.split(_LIVE_CONTEXT_MARKER)[0].strip()
        if head:
            return head[:QUOTE_LIMIT]
    return ""


def format_day_line(now: datetime, data: dict[str, Any], cwd: str = "") -> str:
    """The one line a flush appends: when, where, how much, and what was asked."""
    facts: list[str] = []
    count = data.get("message_count")
    tokens = data.get("token_count")
    if isinstance(count, int):
        facts.append(f"{count} messages")
    if isinstance(tokens, int):
        facts.append(f"~{tokens // 1000}k tokens" if tokens >= 1000 else f"{tokens} tokens")
    where = " ".join(str(cwd or data.get("cwd") or "").split()) or "?"
    ask = _last_user_ask(data.get("history"))
    quote = f' · last ask: "{ask}"' if ask else ""
    return (
        f"- {now.strftime('%H:%M')} · {where} · compaction replaced "
        f"{', '.join(facts) or 'a span'}; no hand-written line existed for it"
        f"{quote} · imp {DEFAULT_IMPORTANCE} · {AUTO_FLUSH_MARKER}"
    )


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
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"# {moment.strftime('%Y-%m-%d (%a)')}\n\n")
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError as e:
        CFG.LOGGER.debug(f"journal day flush could not write {path}: {e}")
        return None
    return path


async def journal_day_flush(context: "HookContext") -> HookResult:
    """The PreCompact hook: record the span before it is replaced."""
    data = context.event_data if isinstance(context.event_data, dict) else {}
    line = format_day_line(datetime.now(), data, cwd=context.cwd or "")
    append_day_line(line)
    return HookResult()


def register_journal_day_flush_hook(manager: "HookManager") -> None:
    """Hook factory: register the flush unless journaling is off, or the hook is
    named in `LLM_HOOKS_DISABLED`."""
    if not CFG.LLM_JOURNAL_ENABLED or not is_builtin_hook_enabled(_NAME):
        return
    manager.add_hook(journal_day_flush, events=[HookEvent.PRE_COMPACT])
