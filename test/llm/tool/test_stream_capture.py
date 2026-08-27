"""Tests for StreamCapture.flush() — the one new surface added so
shell_background.py could self-cap its output under the same ADR-0059
per-tool capping rule shell.py already followed. The retain/echo/spill
behavior itself is already exercised indirectly through test_shell.py; this
file covers only the new method.
"""

import os

from zrb.llm.tool.stream_capture import StreamCapture


def test_flush_before_any_spill_is_a_noop():
    cap = StreamCapture(retain=1000, echo=0)
    cap.feed("short")
    cap.flush()  # must not raise
    assert cap.spill_path is None


def test_flush_makes_fed_content_readable_from_disk():
    cap = StreamCapture(retain=5, echo=0)
    cap.feed("A" * 500)  # exceeds retain -> opens the spill file
    assert cap.spill_path is not None

    cap.flush()
    path = cap.spill_path
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    assert content == "A" * 500

    cap.discard()
    assert not os.path.exists(path)


def test_echoed_text_accumulates_exactly_what_was_echoed():
    """`echoed_text` is what `shell.py` retroactively collapses (see
    `_collapse_shell_output`) — it must reflect exactly what `echo()` sent
    to the console, not the (differently-bounded, tail-biased) `text`
    retained for the model."""
    cap = StreamCapture(retain=1000, echo=1000)
    cap.echo("hello ")
    cap.echo("world")
    assert cap.echoed_text == "hello world"


def test_echoed_text_stops_growing_past_the_echo_budget():
    cap = StreamCapture(retain=1000, echo=5)
    cap.echo("hello world")  # only "hello" fits the budget
    cap.echo("more text")  # budget already spent — nothing more accumulates

    assert "hello" in cap.echoed_text
    assert "world" not in cap.echoed_text
    assert "more text" not in cap.echoed_text


def test_echoed_text_empty_when_echo_budget_is_zero():
    cap = StreamCapture(retain=1000, echo=0)
    cap.echo("hello")
    assert cap.echoed_text == ""
