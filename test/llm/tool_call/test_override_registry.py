from zrb.llm.tool_call.override_registry import pop_override_note, record_override


def test_pop_override_note_returns_none_when_nothing_recorded():
    assert pop_override_note("unknown-call-id") is None


def test_pop_override_note_describes_changed_args():
    record_override(
        "call-1", {"path": "a.txt", "content": "x"}, {"path": "b.txt", "content": "x"}
    )

    note = pop_override_note("call-1")

    assert note is not None
    assert "[SYSTEM NOTE]" in note
    assert "path" in note
    assert "b.txt" in note
    # Unchanged args are not restated.
    assert "content" not in note


def test_pop_override_note_is_one_shot():
    record_override("call-2", {"path": "a.txt"}, {"path": "b.txt"})

    assert pop_override_note("call-2") is not None
    assert pop_override_note("call-2") is None


def test_pop_override_note_returns_none_when_args_are_identical():
    record_override("call-3", {"path": "a.txt"}, {"path": "a.txt"})

    assert pop_override_note("call-3") is None


def test_pop_override_note_truncates_long_values():
    record_override("call-4", {"content": "x"}, {"content": "y" * 500})

    note = pop_override_note("call-4")

    assert note is not None
    assert len(note) < 500
