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
