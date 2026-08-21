"""Tests for StreamCapture.flush() — the one new surface added for H-2
(background-shell output capping). The retain/echo/spill behavior itself is
already exercised indirectly through test_shell.py; this file covers only
the new method.
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
