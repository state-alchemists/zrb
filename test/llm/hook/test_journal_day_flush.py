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


def _context(history, count=42, tokens=96_000, cwd="/repo"):
    return HookContext(
        event=HookEvent.PRE_COMPACT,
        event_data={
            "message_count": count,
            "token_count": tokens,
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
    assert "42 messages" in text and "96k tokens" in text
    assert "· /repo ·" in text, "the line says where the span was compacted"
    assert AUTO_FLUSH_MARKER in text


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

    assert registry.get_hooks(HookEvent.PRE_COMPACT) == [journal_day_flush]


def test_registered_on_pre_compact_only():
    manager = _FakeManager()
    with patch("zrb.llm.hook.journal_day_flush.CFG") as cfg:
        cfg.LLM_JOURNAL_ENABLED = True
        register_journal_day_flush_hook(cast("HookManager", manager))

    assert len(manager.calls) == 1
    _hook, events, _config = manager.calls[0]
    assert events == [HookEvent.PRE_COMPACT]
