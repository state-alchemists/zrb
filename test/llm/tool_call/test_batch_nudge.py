"""The batch nudge: one reminder when lookups went out one call per round."""

import asyncio

from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    UserPromptPart,
)

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


def test_lookups_of_different_tools_are_not_one_streak():
    messages: list = [_prompt(), _call("Read", path="a.py"), _prompt()]
    for tool, arg in (("Grep", "pattern"), ("Glob", "pattern")):
        messages.extend([_call(tool, **{arg: "x"}), _prompt()])

    assert _process(messages) == messages
