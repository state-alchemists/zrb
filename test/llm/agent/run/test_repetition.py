"""Tests for the non-convergence detectors (ADR-0077)."""

from zrb.llm.agent.run.repetition import RepeatedCallDetector, RepetitionDetector

# The shape that motivated the guard: a sentence alternating with a code fence,
# which a strict "same line N times" test would never have caught.
OBSERVED_CYCLE = (
    "I have now created the `MIGRATION.md` file. I will save it to a file.\n```\n"
)


def _feed(detector: RepetitionDetector, text: str) -> bool:
    """Feed *text* one character at a time; return the final verdict.

    Character-at-a-time is the adversarial chunking: a detector that only
    inspected whole deltas would pass a line-at-a-time test and fail here.
    """
    tripped = False
    for char in text:
        tripped = detector.feed(char) or tripped
    return tripped


def test_a_cycling_response_is_flagged():
    detector = RepetitionDetector(window=32)

    tripped = _feed(detector, OBSERVED_CYCLE * 40)

    assert tripped
    assert detector.is_degenerate


def test_prose_that_keeps_saying_something_new_is_not_flagged():
    detector = RepetitionDetector(window=32)
    prose = "".join(
        f"Step {n}: read `module_{n}.py` and note its exports.\n" for n in range(200)
    )

    tripped = _feed(detector, prose)

    assert not tripped
    assert not detector.is_degenerate


def test_a_verdict_does_not_depend_on_how_deltas_are_chunked():
    text = OBSERVED_CYCLE * 40
    by_char = RepetitionDetector(window=32)
    in_one_go = RepetitionDetector(window=32)

    _feed(by_char, text)
    in_one_go.feed(text)

    assert by_char.is_degenerate == in_one_go.is_degenerate is True


def test_a_short_burst_of_repetition_is_left_alone():
    """A model may legitimately repeat a few lines — a table, a list of imports."""
    detector = RepetitionDetector(window=32)

    tripped = _feed(detector, "from app.auth import new_auth\n" * 10)

    assert not tripped


def test_window_of_zero_disables_the_guard():
    detector = RepetitionDetector(window=0)

    tripped = _feed(detector, OBSERVED_CYCLE * 100)

    assert not tripped
    assert not detector.is_degenerate


def test_blank_lines_do_not_count_toward_the_window():
    """Otherwise a run of blank lines alone would trip it."""
    detector = RepetitionDetector(window=8)

    tripped = _feed(detector, "\n" * 200)

    assert not tripped


def test_reset_forgets_the_previous_response():
    detector = RepetitionDetector(window=32)
    _feed(detector, OBSERVED_CYCLE * 40)
    assert detector.is_degenerate

    detector.reset()

    assert not detector.is_degenerate


def test_an_unterminated_line_is_not_judged():
    """Only completed lines are judged, so a partial delta cannot trip it."""
    detector = RepetitionDetector(window=4)

    tripped = detector.feed("a line with no newline yet")

    assert not tripped


# ── The same call, back to back ─────────────────────────────────────────


def test_an_identical_call_repeated_past_the_limit_is_refused():
    """The observed shape: the same grep, ~100 times, after the work was done."""
    detector = RepeatedCallDetector(limit=6)
    args = {"pattern": r"new_auth\("}

    verdicts = [detector.check("Grep", args) for _ in range(10)]

    assert verdicts[:6] == [False] * 6, "refused before the limit was reached"
    assert all(verdicts[6:]), "kept executing past the limit"


def test_a_run_fix_run_cycle_is_not_a_loop():
    """The same `pytest` many times is the debug loop working, not failing.

    An `Edit` lands between the runs, so the streak resets -- which is the whole
    reason the counter is consecutive rather than cumulative.
    """
    detector = RepeatedCallDetector(limit=6)
    cycle = [("Shell", {"command": "pytest"}), ("Edit", {"path": "a.py"})] * 20

    assert not any(detector.check(name, args) for name, args in cycle)


def test_a_polling_tool_may_repeat_forever():
    detector = RepeatedCallDetector(limit=6)

    assert not any(
        detector.check("MonitorProcess", {"handle": "h1"}) for _ in range(50)
    )


def test_changed_arguments_reset_the_streak():
    detector = RepeatedCallDetector(limit=3)

    for i in range(20):
        assert not detector.check("Read", {"path": f"file_{i}.py"})


def test_key_order_does_not_hide_a_repeat():
    """A provider that reorders keys between calls is still repeating itself."""
    detector = RepeatedCallDetector(limit=2)

    detector.check("Edit", {"path": "a.py", "old_string": "x"})
    detector.check("Edit", {"old_string": "x", "path": "a.py"})

    assert detector.check("Edit", {"path": "a.py", "old_string": "x"})


def test_a_limit_of_zero_disables_the_guard():
    detector = RepeatedCallDetector(limit=0)

    assert not any(detector.check("Grep", {"pattern": "x"}) for _ in range(100))


def test_unserializable_arguments_do_not_raise():
    detector = RepeatedCallDetector(limit=2)

    class Opaque:
        pass

    args = {"handle": Opaque()}
    assert not any(detector.check("Weird", args) for _ in range(2))
