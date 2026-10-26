"""The built-in day flush: a compaction is written into the journal's day tier.

Registered on every `HookManager` whenever `LLM_JOURNAL_ENABLED` and
`LLM_JOURNAL_DAY_FLUSH_ENABLED` are both on, so a journaled setup gets a day
record without configuring anything. It listens to `PostCompact`, which fires on
every turn, and writes only when the turn replaced history: writing on every turn
would put one line per turn in the day file.

It takes no model call and makes no judgement about what mattered. One line
records which span went away, how big it was, and the last thing the user asked.
A model-driven "keep the five lines worth keeping" pass belongs in a slower hook.

A failure here must never block anything: the writer catches its own errors and
the hook always returns a result with no output.
"""

import os
import re
from datetime import datetime
from typing import TYPE_CHECKING

from zrb.config.config import CFG
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
"""The importance a flushed line gets. It is scaffolding the sweep may drop."""

AUTO_FLUSH_MARKER = "auto-flush"
# The injected block ends the turn and closes its own tag, so only that shape is
# removed: a user writing `<live-context>` mid-sentence keeps his words.
_TRAILING_LIVE_CONTEXT = re.compile(
    r"\s*<live-context>.*?</live-context>\s*\Z", re.DOTALL
)


def _day_path(now: datetime, root: str | None = None) -> str:
    """The day file for *now* under the journal directory."""
    base = os.path.abspath(
        os.path.expanduser(root if root is not None else CFG.LLM_JOURNAL_DIR)
    )
    return os.path.join(base, DAY_DIR_NAME, f"{now.strftime('%Y-%m-%d')}.md")


def _parts_of(message: object) -> "list[object] | None":
    """*message*'s parts, when it has any; ``None`` for a bare string or part."""
    parts = (
        message.get("parts")
        if isinstance(message, dict)
        else getattr(message, "parts", None)
    )
    return list(parts) if isinstance(parts, (list, tuple)) else None


def _content_of(part: object) -> object:
    """A part's own content, whichever way the part arrived."""
    if isinstance(part, dict):
        return part.get("content")
    return getattr(part, "content", None)


def _part_kind(part: object) -> str:
    """A part's `part_kind`, whichever way the part arrived."""
    kind = part.get("part_kind") if isinstance(part, dict) else getattr(part, "part_kind", None)
    return str(kind or "")


def _user_text(message: object) -> str:
    """The words of *message* the user typed, and no other part of it.

    A `ModelRequest` carries a system prompt and tool returns beside the user's
    turn, so its parts are filtered by `part_kind` rather than trusted whole —
    otherwise a tool result becomes "the last thing the user asked". A bare
    string, and a message with no parts, are taken as they are.
    """
    parts = _parts_of(message)
    if parts is None:
        return _words(message)
    return " ".join(
        _words(_content_of(part))
        for part in parts
        if _part_kind(part).startswith("user")
    )


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

    The live-context block rides at the end of the turn, so only a trailing block
    is cut: a turn that merely mentions the tag is still the user's sentence.
    """
    words = _TRAILING_LIVE_CONTEXT.sub("", _words(message))
    return " ".join(words.split())[:QUOTE_LIMIT]


def _last_user_ask(data: dict[str, object]) -> str:
    """What the user last asked: this turn's prompt, else the newest turn in history.

    `_prepare_history` sends the prompt with the event, because it joins the
    history only afterwards. When no prompt came with the event, the newest user
    turn in the history is used, and only its user-prompt parts: a system prompt or
    a tool return is not something anybody asked.
    """
    prompt = data.get("prompt")
    if prompt is not None:
        asked = _typed_text(prompt)
        if asked:
            return asked
    history = data.get("history")
    for message in reversed(history if isinstance(history, list) else []):
        asked = _typed_text(_user_text(message))
        if asked:
            return asked
    return ""


def _span(count_key: str, token_key: str, data: dict[str, object]) -> str:
    """`42 messages, ~96k tokens` for one side of a compaction, or `a span`."""
    facts: list[str] = []
    count = data.get(count_key)
    tokens = data.get(token_key)
    if isinstance(count, int):
        facts.append(f"{count} messages")
    if isinstance(tokens, int):
        facts.append(
            f"~{tokens // 1000}k tokens" if tokens >= 1000 else f"{tokens} tokens"
        )
    return ", ".join(facts) or "a span"


def format_day_line(now: datetime, data: dict[str, object], cwd: str = "") -> str:
    """The one line a flush appends: when, where, how much, and what was asked."""
    where = " ".join(str(cwd or data.get("cwd") or "").split()) or "?"
    ask = _last_user_ask(data)
    quote = f' · last ask: "{ask}"' if ask else ""
    replaced = _span("before_message_count", "before_token_count", data)
    kept = _span("message_count", "token_count", data)
    return (
        f"- {now.strftime('%H:%M')} · {where} · compaction replaced {replaced} "
        f"with {kept}{quote} · imp {DEFAULT_IMPORTANCE} · {AUTO_FLUSH_MARKER}"
    )


def append_day_line(
    line: str, now: datetime | None = None, root: str | None = None
) -> "str | None":
    """Append *line* to the day file, with its heading when the file is new.

    Returns the path written, or ``None`` when the write failed — the caller
    treats that as "no flush", never as an error to report upward.

    The heading is written with the first line rather than in a separate create
    step: one session would create an empty file, another would append its line,
    and the first would then write the heading over the start of it. One append
    puts each line at the end of the file, so nothing is overwritten. Two sessions
    arriving together can both write a heading; a duplicate is better than a loss.
    """
    moment = now or datetime.now()
    path = _day_path(moment, root)
    heading = f"# {moment.strftime('%Y-%m-%d (%a)')}\n\n"
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            new = os.fstat(f.fileno()).st_size == 0
            f.write((heading if new else "") + line + "\n")
    except OSError as e:
        CFG.LOGGER.debug(f"journal day flush could not write {path}: {e}")
        return None
    return path


class _DayFlush:
    """The flush as a callable that carries its own name.

    `HookRegistry._hook_name` reads a config's name, then the hook's `__name__`,
    then its `name`. A plain function answers with its Python name,
    `journal_day_flush`, which `LLM_HOOKS=journal-day-flush` does not match, so an
    allowlist naming the flush would have dropped it silently. An object has no
    `__name__`, so the documented name is the one that answers.
    """

    name = _NAME

    async def __call__(self, context: "HookContext") -> HookResult:
        """The PostCompact hook: record the span a compaction replaced.

        Nothing is written when the turn replaced no history. Both compaction
        events fire on every turn, so a hook that wrote on each would put one line
        per turn in the day file.
        """
        data = context.event_data if isinstance(context.event_data, dict) else {}
        if not data.get("compacted"):
            return HookResult()
        line = format_day_line(datetime.now(), data, cwd=context.cwd or "")
        append_day_line(line)
        return HookResult()


journal_day_flush = _DayFlush()
"""The one flush hook; see `_DayFlush` for why it is an object rather than a function."""


def register_journal_day_flush_hook(manager: "HookManager") -> None:
    """Hook factory: register the flush unless journaling is off, or
    `LLM_JOURNAL_DAY_FLUSH_ENABLED` says no. Its own switch exists so the flush can
    be left out while the rest of journaling carries on — the same shape
    `LLM_SELF_REVIEW_ENABLED` gives the self-review gate."""
    if not CFG.LLM_JOURNAL_ENABLED or not CFG.LLM_JOURNAL_DAY_FLUSH_ENABLED:
        return
    manager.add_hook(journal_day_flush, events=[HookEvent.POST_COMPACT])
