from types import SimpleNamespace

import pytest

from zrb.llm.speech.progress import (
    ProgressNarrator,
    SpeechClock,
    describe_tool_progress,
)


def _call(tool, call_id="c1"):
    return SimpleNamespace(
        event_kind="function_tool_call",
        part=SimpleNamespace(tool_name=tool, tool_call_id=call_id),
    )


def _result(call_id="c1", nested=False):
    if nested:
        return SimpleNamespace(
            event_kind="function_tool_result",
            result=SimpleNamespace(tool_call_id=call_id),
        )
    return SimpleNamespace(event_kind="function_tool_result", tool_call_id=call_id)


def _narrator(silence=100.0, interval=8.0):
    said = []
    narrator = ProgressNarrator(
        lambda text, is_stale: said.append((text, is_stale)),
        lambda: silence,
        interval,
    )
    return narrator, said


@pytest.mark.parametrize(
    "tool, line",
    [
        ("Shell", "Running a command."),
        ("Grep", "Searching the code."),
        ("LspFindReferences", "Checking the code."),
        ("Deploy", "Using the Deploy tool."),
        (None, "Working on it."),
    ],
)
def test_describe_tool_progress(tool, line):
    assert describe_tool_progress(tool) == line


def test_a_tool_call_after_a_silence_is_announced_until_it_finishes():
    narrator, said = _narrator()

    narrator.handle_event(_call("Shell"))

    [(text, is_stale)] = said
    assert text == "Running a command."
    assert is_stale() is False
    narrator.handle_event(_result())
    assert is_stale() is True


def test_a_result_naming_its_call_through_the_result_part_counts_too():
    narrator, said = _narrator()
    narrator.handle_event(_call("Shell", "c9"))
    narrator.handle_event(_result("c9", nested=True))
    assert said[0][1]() is True


def test_nothing_is_announced_right_after_speech():
    narrator, said = _narrator(silence=2.0)
    narrator.handle_event(_call("Shell"))
    assert said == []


def test_bookkeeping_tools_and_a_zero_interval_are_silent():
    narrator, said = _narrator()
    narrator.handle_event(_call("TodoWrite"))
    assert said == []

    narrator, said = _narrator(interval=0)
    narrator.handle_event(_call("Shell"))
    assert said == []


def test_other_events_are_ignored():
    narrator, said = _narrator()
    narrator.handle_event(SimpleNamespace(event_kind="part_start"))
    assert said == []


def test_the_clock_counts_from_the_last_mark():
    clock = SpeechClock()
    assert clock.seconds_since_said() == float("inf")
    clock.mark()
    assert 0 <= clock.seconds_since_said() < 1


def test_the_silent_tools_are_configured():
    said = []
    narrator = ProgressNarrator(
        lambda text, is_stale: said.append(text),
        lambda: 100.0,
        8.0,
        silent_tools=["Shell"],
    )
    narrator.handle_event(_call("Shell"))
    narrator.handle_event(_call("TodoWrite", "c2"))
    assert said == ["Using the TodoWrite tool."]


def test_progress_lines_come_from_the_configured_patterns_in_order():
    phrases = {
        "Read": "Membaca berkas.",
        "Lsp*": "Memeriksa kode.",
        "*": "Pakai {tool}.",
    }
    assert describe_tool_progress("Read", phrases) == "Membaca berkas."
    assert describe_tool_progress("LspHover", phrases) == "Memeriksa kode."
    assert describe_tool_progress("Grep", phrases) == "Pakai Grep."


def test_a_tool_no_pattern_matches_is_not_announced():
    said = []
    narrator = ProgressNarrator(
        lambda text, is_stale: said.append(text),
        lambda: 100.0,
        8.0,
        phrases={"Shell": "Running a command."},
    )
    narrator.handle_event(_call("Grep"))
    narrator.handle_event(_call("Shell", "c2"))
    assert said == ["Running a command."]


def test_progress_lines_are_read_from_cfg_when_left_unset(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_SPEECH_PROGRESS_PHRASES", '{"*": "Sedang {tool}."}')
    assert describe_tool_progress("Read") == "Sedang Read."


def test_a_turn_that_stops_while_the_line_is_being_decided_on_is_not_announced():
    """A stop landing between the silence check and the queue wins: the line
    would otherwise be spoken after the turn had stopped (review on #579)."""
    said = []
    holder = {}

    def seconds_since_said():
        holder["narrator"].reset()
        return 100.0

    narrator = ProgressNarrator(
        lambda text, is_stale: said.append((text, is_stale)),
        seconds_since_said,
        8.0,
    )
    holder["narrator"] = narrator

    narrator.handle_event(_call("Shell"))

    assert said == []


def test_a_reused_call_id_does_not_resurrect_a_line_from_an_earlier_turn():
    """Clearing `_running` alone cannot invalidate a queued line: a later turn
    may reuse the id, so the line carries its generation (review on #579)."""
    narrator, said = _narrator()

    narrator.handle_event(_call("Shell", "c1"))
    [(_, from_the_earlier_turn)] = said
    narrator.reset()
    narrator.handle_event(_call("Shell", "c1"))
    _, from_this_turn = said[1]

    assert from_the_earlier_turn() is True
    assert from_this_turn() is False


def test_a_late_result_from_an_earlier_turn_does_not_drop_the_new_turns_call():
    """A result names only its call id, so one left over from a stopped turn
    must not clear the call a later turn starts under the same id (review on
    #579)."""
    narrator, said = _narrator()

    narrator.handle_event(_call("Shell", "c1"))  # turn one starts "c1"
    narrator.reset()  # turn one stops with it still running
    narrator.handle_event(_call("Shell", "c1"))  # turn two reuses "c1"
    _, from_this_turn = said[1]
    assert from_this_turn() is False

    narrator.handle_event(_result("c1"))  # turn one's result, delivered late

    assert from_this_turn() is False  # turn two's call is still running

    narrator.handle_event(_result("c1"))  # turn two's own result

    assert from_this_turn() is True
