"""Tests for the built-in day flush (`journal-day-flush`).

The flush rides on compaction, which is already the most expensive moment of a
session. These tests pin the three properties that keep it safe there: it
writes exactly one line, it quotes only what the user typed, and a failure is
swallowed rather than raised into the compaction path.
"""

import asyncio
from datetime import datetime
from typing import cast
from unittest.mock import patch

from zrb.llm.hook.interface import HookContext
from zrb.llm.hook.journal_day_flush import (
    AUTO_FLUSH_MARKER,
    append_day_line,
    format_day_line,
    journal_day_flush,
    register_journal_day_flush_hook,
)
from zrb.llm.hook.manager import HookManager
from zrb.llm.hook.registry import HookRegistry
from zrb.llm.hook.types import HookEvent

NOW = datetime(2026, 10, 26, 20, 30)


class _FakeManager:
    """Records what a real manager would have been asked to register."""

    def __init__(self):
        self.calls = []

    def add_hook(self, hook, events=None, config=None):
        self.calls.append((hook, events, config))


def _context(history, count=42, tokens=96_000, cwd="/repo", compacted=True):
    return HookContext(
        event=HookEvent.POST_COMPACT,
        event_data={
            "message_count": count,
            "token_count": tokens,
            "before_message_count": 148,
            "before_token_count": 240_000,
            "compacted": compacted,
            "has_history_processors": True,
            "history": history,
        },
        cwd=cwd,
    )


def test_the_flush_writes_one_line_into_todays_day_file(tmp_path):
    with patch("zrb.llm.hook.journal_day_flush.CFG") as cfg:
        cfg.LLM_JOURNAL_DIR = str(tmp_path)
        asyncio.run(
            journal_day_flush(
                _context([{"parts": [{"content": "check the pipeline", "part_kind": "user-prompt"}]}])
            )
        )

    day_file = next((tmp_path / "days").iterdir())
    text = day_file.read_text(encoding="utf-8")
    assert text.startswith("# "), "a new day file opens with its heading"
    assert text.count("\n- ") == 1, "one line per flush"
    assert "replaced 148 messages, ~240k tokens with 42 messages, ~96k tokens" in text
    assert "· /repo ·" in text, "the line says where the span was compacted"
    assert AUTO_FLUSH_MARKER in text


def test_nothing_is_written_when_the_turn_replaced_nothing(tmp_path):
    """Both compaction events fire on every turn. A hook that wrote on each would
    put one line in the day file per turn, which is noise wearing a record's shape."""
    with patch("zrb.llm.hook.journal_day_flush.CFG") as cfg:
        cfg.LLM_JOURNAL_DIR = str(tmp_path)
        asyncio.run(journal_day_flush(_context([], count=148, tokens=240_000, compacted=False)))

    assert not (tmp_path / "days").exists()


def test_only_the_typed_text_is_quoted():
    """The live-context block rides inside the user turn; it is not his words."""
    history = [
        {
            "parts": [
                {
                    "content": "fix the retry block\n\n<live-context> - Time: 20:00 </live-context>",
                    "part_kind": "user-prompt",
                }
            ]
        }
    ]
    line = format_day_line(NOW, {"history": history}, cwd="/repo")

    assert 'last ask: "fix the retry block"' in line
    assert "<live-context>" not in line


def test_a_mention_of_the_tag_keeps_the_users_words():
    """Only a trailing injected block is removed: a turn that asks about the tag
    itself is still the user's sentence, not something to cut at."""
    line = format_day_line(
        NOW, {"prompt": 'please explain the "<live-context>" tag'}, cwd="/repo"
    )

    assert 'last ask: "please explain the "<live-context>" tag"' in line


def test_the_prompt_that_caused_it_is_what_is_quoted():
    """`_prepare_history` fires PRE_COMPACT before the prompt joins the history, so
    the prompt is the only place the ask that caused this compaction can come from."""
    history = [{"parts": [{"content": "the previous ask", "part_kind": "user-prompt"}]}]

    line = format_day_line(
        NOW, {"history": history, "prompt": "start the sweep tonight"}, cwd="/repo"
    )

    assert 'last ask: "start the sweep tonight"' in line
    assert "the previous ask" not in line


def test_a_compaction_nothing_asked_for_falls_back_to_the_history():
    """The prompt is missing when nothing prompted it: the newest user turn is then
    the best there is."""
    history = [{"parts": [{"content": "the ask in flight", "part_kind": "user-prompt"}]}]

    line = format_day_line(NOW, {"history": history}, cwd="/repo")

    assert 'last ask: "the ask in flight"' in line


def test_a_prompt_with_an_attachment_keeps_its_words():
    """A prompt that carried an attachment arrives as a flat list: the text, the
    attachment, then the live-context block. The words are still the ask."""

    class Attachment:  # what an image looks like from here: content, no parts
        content = b"\x89PNG"

    prompt = [
        "look at this papaya",
        Attachment(),
        "<live-context> - Time: 20:00 </live-context>",
    ]

    line = format_day_line(NOW, {"prompt": prompt}, cwd="/repo")

    assert 'last ask: "look at this papaya"' in line
    assert "<live-context>" not in line


def test_object_shaped_history_is_read_too():
    """A Python caller hands over live `ModelRequest` objects, not JSON."""

    class Part:
        part_kind = "user-prompt"

        def __init__(self, content):
            self.content = content

    class Message:
        kind = "request"

        def __init__(self, content):
            self.parts = [Part(content)]

    line = format_day_line(NOW, {"history": [Message("are we done for the day?")]})

    assert 'last ask: "are we done for the day?"' in line


def test_appending_never_truncates_an_existing_day_file(tmp_path):
    """The day tier is append-only: a flush adds its line and leaves every earlier
    one. The second call is also the case where the file already exists, so the
    heading is written once rather than overwriting the morning's record."""
    first = append_day_line("- 09:00 · home · the morning line · imp 9", now=NOW, root=str(tmp_path))
    second = append_day_line("- 20:30 · home · the evening line · imp 2", now=NOW, root=str(tmp_path))

    assert first == second
    text = (tmp_path / "days" / "2026-10-26.md").read_text(encoding="utf-8")
    assert text.count("# ") == 1, "the heading is written once"
    assert "the morning line" in text and "the evening line" in text


def test_an_attachment_in_the_history_is_never_stringified_into_the_quote():
    """A user part may hold a list: the text, then the attachment. `str` of that
    list carries the attachment's bytes, so only the words are taken — the quote
    must not become a Python repr of somebody's image."""

    class Part:
        part_kind = "user-prompt"

        def __init__(self, content):
            self.content = content

    class Message:
        kind = "request"

        def __init__(self, content):
            self.parts = [Part(content)]

    class Image:  # what an image part looks like from here: data, no content
        media_type = "image/png"
        data = b"\x89PNG-not-words"

    line = format_day_line(
        NOW, {"history": [Message(["look at this papaya", Image()])]}, cwd="/repo"
    )

    assert 'last ask: "look at this papaya"' in line
    assert "PNG" not in line, "an attachment's bytes are not words anyone typed"


def test_a_failed_write_returns_none_instead_of_raising(tmp_path):
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("x", encoding="utf-8")

    written = append_day_line("- line", now=NOW, root=str(blocker))

    assert written is None


def test_no_flush_when_journaling_is_off():
    manager = _FakeManager()
    with patch("zrb.llm.hook.journal_day_flush.CFG") as cfg:
        cfg.LLM_JOURNAL_ENABLED = False
        register_journal_day_flush_hook(cast("HookManager", manager))

    assert manager.calls == []


def test_an_allowlist_naming_the_flush_keeps_it(monkeypatch):
    """`LLM_HOOKS` is an allowlist of hook names, so the flush has to answer to its
    own name — not to the Python name of whatever implements it."""
    registry = HookRegistry()
    manager = HookManager(registry=registry)
    monkeypatch.setenv("ZRB_LLM_HOOKS", "journal-day-flush")
    with patch("zrb.llm.hook.journal_day_flush.CFG") as cfg:
        cfg.LLM_JOURNAL_ENABLED = True
        register_journal_day_flush_hook(cast("HookManager", manager))

    assert registry.get_hooks(HookEvent.POST_COMPACT) == [journal_day_flush]


def test_registered_on_post_compact_only():
    manager = _FakeManager()
    with patch("zrb.llm.hook.journal_day_flush.CFG") as cfg:
        cfg.LLM_JOURNAL_ENABLED = True
        register_journal_day_flush_hook(cast("HookManager", manager))

    assert len(manager.calls) == 1
    _hook, events, _config = manager.calls[0]
    assert events == [HookEvent.POST_COMPACT]
