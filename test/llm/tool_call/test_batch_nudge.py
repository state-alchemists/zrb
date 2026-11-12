"""The batch nudge: one reminder per turn, when lookups went out one call per round."""

import asyncio

from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

from zrb.llm.tool_call import batch_nudge
from zrb.llm.tool_call.batch_nudge import (
    NUDGE_MARKER,
    STREAK_LENGTH,
    create_batch_nudge_processor,
)


def _prompt(text: str = "do the thing") -> ModelRequest:
    return ModelRequest(parts=[UserPromptPart(content=text)])


def _call(tool_name: str, **args) -> ModelResponse:
    return ModelResponse(parts=[ToolCallPart(tool_name=tool_name, args=args)])


def _batched(tool_name: str, *paths: str) -> ModelResponse:
    return ModelResponse(
        parts=[ToolCallPart(tool_name=tool_name, args={"path": path}) for path in paths]
    )


def _answer(text: str = "done") -> ModelResponse:
    return ModelResponse(parts=[TextPart(text)])


def _process(messages: list) -> list:
    """Run the processor as the runner does, overhead argument included."""
    processor = create_batch_nudge_processor()
    return asyncio.run(processor(messages, 1000))


def _nudge_text(messages: list) -> str:
    return "".join(
        part.content
        for part in messages[-1].parts
        if isinstance(getattr(part, "content", None), str)
    )


def _read_streak(paths: list[str]) -> list:
    messages: list = [_prompt()]
    for path in paths:
        messages.append(_call("Read", path=path))
        messages.append(_prompt())
    return messages


def _result(tool_name: str = "Read", content: object = "ok") -> ModelRequest:
    """One call's result, the message a run records a round as ending with."""
    return ModelRequest(parts=[ToolReturnPart(tool_name=tool_name, content=content)])


def _serial_rounds(paths: list[str]) -> list:
    """Rounds in the run's own shape: one call, then that call's result.

    `_read_streak` puts a user prompt after every call, which the runner does
    not do; the turn rule turns on that difference, so the tests about turns
    are written this way.
    """
    messages: list = []
    for path in paths:
        messages.extend([_call("Read", path=path), _result()])
    return messages


def _result_with_prompt(text: str) -> ModelRequest:
    """A request holding a tool return and a user prompt together.

    That is what a tool result carrying an image looks like once saved, and
    what `merge_consecutive_messages` builds when someone types while a tool is
    still running.
    """
    return ModelRequest(
        parts=[
            ToolReturnPart(tool_name="Read", content="ok"),
            UserPromptPart(content=text),
        ]
    )


def test_a_streak_of_single_lookups_gets_one_nudge():
    messages = _read_streak(["a.py", "b.py", "c.py"])

    result = _process(messages)

    assert len(result) == len(messages) + 1
    assert NUDGE_MARKER in _nudge_text(result)
    assert "`Read`" in _nudge_text(result)


def test_the_streak_length_is_what_triggers_it():
    messages = _read_streak(["a.py", "b.py"])
    assert STREAK_LENGTH == 3
    assert _process(messages) == messages


def test_calls_on_the_same_argument_are_not_independent():
    messages = _read_streak(["a.py", "a.py", "a.py"])

    assert _process(messages) == messages


def test_a_tool_whose_calls_depend_on_each_other_is_never_nudged():
    messages: list = [_prompt()]
    for command in ("pytest -q", "git status", "ruff check"):
        messages.extend([_call("Shell", command=command), _prompt()])

    assert _process(messages) == messages


def test_a_round_that_already_batched_silences_it():
    messages: list = [_prompt(), _call("Read", path="a.py"), _prompt()]
    messages.extend([_batched("Read", "b.py", "c.py"), _prompt()])
    messages.extend([_call("Read", path="d.py"), _prompt()])

    assert _process(messages) == messages


def test_a_finished_answer_ends_the_tail():
    messages = _read_streak(["a.py", "b.py", "c.py"])
    messages.append(_answer())

    assert _process(messages) == messages


def test_the_nudge_is_not_repeated_while_it_is_still_in_the_history():
    messages = _read_streak(["a.py", "b.py", "c.py"])
    messages.append(_prompt(f"{NUDGE_MARKER} — batch them."))

    assert _process(messages) == messages


def test_a_streak_after_the_nudge_gets_a_fresh_one():
    messages = _read_streak(["a.py", "b.py", "c.py"])
    messages.append(_prompt(f"{NUDGE_MARKER} — batch them."))
    messages.extend([_call("Read", path="d.py"), _prompt()])
    messages.extend([_call("Read", path="e.py"), _prompt()])
    messages.extend([_call("Read", path="f.py"), _prompt()])

    # The earlier nudge no longer sits between the model and the pattern.
    assert len(_process(messages)) == len(messages) + 1


def test_a_second_streak_in_the_same_turn_is_not_reminded_again():
    """Once per turn, however long the turn runs.

    The reminder belongs to the turn that caused it: a model that answers it
    with three more single lookups is not told again, which is what the module
    means by saying it once rather than every round after. Replayed over 645
    saved conversations, the walk as it stood put 23 of its 80 reminders into a
    stretch that had none since the reminder before it.
    """
    messages = [_prompt(), *_serial_rounds(["a.py", "b.py", "c.py"])]
    nudged = _process(messages)
    assert NUDGE_MARKER in _nudge_text(nudged)

    continued = nudged + _serial_rounds(["d.py", "e.py", "f.py"])

    assert _process(continued) == continued


def test_a_streak_in_a_new_turn_is_reminded_again():
    """A new turn is a new question, so the rule is available to be said again.

    This is the half that keeps "at most once per turn" from meaning "once per
    conversation": the turn that begins later — a new task, an hour on — is the
    one where a model drifts back to one lookup per round, and the reminder it
    earned earlier is history by then.
    """
    messages = [_prompt(), *_serial_rounds(["a.py", "b.py", "c.py"])]
    nudged = _process(messages)

    later = [*nudged, _prompt("now the other thing")]
    later.extend(_serial_rounds(["g.py", "h.py", "i.py"]))

    result = _process(later)

    assert len(result) == len(later) + 1
    assert NUDGE_MARKER in _nudge_text(result)


def test_a_nudge_before_the_latest_prompt_does_not_silence_the_newest_turn():
    """A reminder from the turn before is history, not a muzzle.

    Two rounds, the reminder they earned, then a new prompt and one more
    lookup: the walk still has three single-call rounds to count, and the
    reminder standing between them belongs to the turn that just ended. The
    old scan stopped at that marker, which is why a streak running across a
    turn boundary never reached the model at all.
    """
    messages = [_prompt(), *_serial_rounds(["a.py", "b.py"])]
    messages.append(_prompt(f"{NUDGE_MARKER} — batch them."))
    messages.append(_prompt("and one more thing"))
    messages.extend(_serial_rounds(["c.py"]))

    result = _process(messages)

    assert len(result) == len(messages) + 1
    assert NUDGE_MARKER in _nudge_text(result)


def test_a_prompt_merged_with_a_tool_return_does_not_start_a_turn():
    """A turn starts at a request the person is speaking in, not at a result.

    A tool result saved with an image, or a prompt merged into the request that
    returned a tool's output, carries a `UserPromptPart` without being someone
    starting a turn. Reading it as one would re-arm the reminder mid-turn.
    """
    messages = [_prompt(), *_serial_rounds(["a.py", "b.py", "c.py"])]
    nudged = _process(messages)
    assert NUDGE_MARKER in _nudge_text(nudged)

    continued = nudged + [_result_with_prompt("attached")]
    continued.extend(_serial_rounds(["d.py", "e.py", "f.py"]))

    assert _process(continued) == continued


def test_a_tool_result_quoting_the_marker_is_not_a_reminder():
    """Reading this module's own source must not silence the reminder.

    The marker is a string literal in `batch_nudge.py`, so a `Read` of it puts
    those words into a tool result — here as the first round of the streak.
    Scanning every part of every message for them made the walk stop on its own
    source, and a session auditing this feature never heard from it again.
    """
    messages = [_prompt(), _call("Read", path="batch_nudge.py")]
    messages.append(_result(content=f'NUDGE_MARKER = "{NUDGE_MARKER}"'))
    messages.extend(_serial_rounds(["a.py", "b.py"]))

    result = _process(messages)

    assert len(result) == len(messages) + 1
    assert NUDGE_MARKER in _nudge_text(result)


def test_lookups_of_different_tools_are_one_streak():
    """A lookup streak is one streak whether or not the tool changes.

    None of these calls needs the last one's output: the model is looking at
    three things one round apart, and one response would have done it.
    """
    messages: list = [_prompt(), _call("Read", path="a.py"), _prompt()]
    for tool, arg in (("Grep", "pattern"), ("Glob", "pattern")):
        messages.extend([_call(tool, **{arg: "x"}), _prompt()])

    result = _process(messages)

    assert len(result) == len(messages) + 1
    assert NUDGE_MARKER in _nudge_text(result)
    assert "a single lookup" in _nudge_text(result)


def test_a_shell_command_in_the_middle_ends_the_streak():
    """Widening the streak to mixed lookups must not carry it across a call
    that may have produced the arguments of the next one."""
    messages: list = [_prompt(), _call("Read", path="a.py"), _prompt()]
    messages.extend([_call("Shell", command="pytest -q"), _prompt()])
    messages.extend([_call("Read", path="b.py"), _prompt()])

    assert _process(messages) == messages


def test_the_reminder_is_off_when_its_knob_is_off(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_BATCH_TOOL_CALL_NUDGE_ENABLED", "off")
    messages = _read_streak(["a.py", "b.py", "c.py"])

    assert _process(messages) == messages


def test_a_model_known_to_malform_parallel_calls_is_not_reminded(monkeypatch):
    """The System Context already withdrew the batch rule for this model; a
    reminder pushing the other way would cost it both calls in the round.

    `minimax-m2.7` is on `_NO_PARALLEL_TOOL_CALLS`; a model merely absent from
    that list is unknown, not able, and keeps the reminder (next test).
    """
    monkeypatch.setattr(batch_nudge, "get_current_model", lambda: "minimax-m2.7")
    messages = _read_streak(["a.py", "b.py", "c.py"])

    assert _process(messages) == messages


def test_an_unknown_model_keeps_the_reminder(monkeypatch):
    """`None` is unknown, not a `False`: an unlisted model is assumed able."""
    monkeypatch.setattr(
        batch_nudge, "get_current_model", lambda: "ollama:some-local-model"
    )
    messages = _read_streak(["a.py", "b.py", "c.py"])

    assert len(_process(messages)) == len(messages) + 1
