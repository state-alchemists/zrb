"""The tool-result payload reaches the model exactly once.

``ToolReturn.content`` is delivered as a *separate* ``UserPromptPart`` beside the
tool result, so restating the result there both doubles its token cost and
appends a spurious user turn after every tool call. These tests pin the
invariant end-to-end: whatever a zrb-wrapped tool returns appears once, in the
tool-result message, and no user turn follows it.
"""

import pytest

PAYLOAD = "PAYLOAD-MARKER-9f3a1c"


def _function_model(captured: list):
    """A FunctionModel that calls ``probe`` once, then answers."""
    from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart
    from pydantic_ai.models.function import FunctionModel

    state = {"calls": 0}

    def respond(messages, info):
        captured.append(messages)
        state["calls"] += 1
        if state["calls"] == 1:
            return ModelResponse(parts=[ToolCallPart("probe", {"x": "q"})])
        return ModelResponse(parts=[TextPart("done")])

    return FunctionModel(respond)


def _payload_occurrences(messages) -> int:
    return sum(
        str(getattr(part, "content", "")).count(PAYLOAD)
        for message in messages
        for part in message.parts
    )


@pytest.mark.asyncio
async def test_tool_result_reaches_model_once_and_adds_no_user_turn():
    from pydantic_ai import Agent

    from zrb.llm.agent.common import create_safe_wrapper

    captured: list = []

    def probe(x: str) -> dict:
        return {"payload": PAYLOAD}

    agent = Agent(_function_model(captured))
    agent.tool_plain(create_safe_wrapper(probe, name="probe"))

    result = await agent.run("go")

    # Exactly one copy in what the model was sent on its second request.
    assert _payload_occurrences(captured[-1]) == 1

    # The tool result arrives as a tool-return, and nothing masquerades as a
    # new user turn after it (only the opening prompt is a user turn).
    kinds = [
        [part.part_kind for part in message.parts] for message in result.all_messages()
    ]
    assert kinds == [["user-prompt"], ["tool-call"], ["tool-return"], ["text"]]


@pytest.mark.asyncio
async def test_toolset_result_reaches_model_once_and_adds_no_user_turn():
    from pydantic_ai import Agent
    from pydantic_ai.toolsets import FunctionToolset

    from zrb.llm.agent.common import wrap_toolset

    captured: list = []

    def probe(x: str) -> dict:
        return {"payload": PAYLOAD}

    agent = Agent(
        _function_model(captured),
        toolsets=[wrap_toolset(FunctionToolset(tools=[probe]))],
    )

    result = await agent.run("go")

    assert _payload_occurrences(captured[-1]) == 1
    kinds = [
        [part.part_kind for part in message.parts] for message in result.all_messages()
    ]
    assert kinds == [["user-prompt"], ["tool-call"], ["tool-return"], ["text"]]


@pytest.mark.asyncio
async def test_tool_error_reaches_model_as_the_tool_result():
    """A failing tool reports through the tool result, not a null plus a user turn."""
    from pydantic_ai import Agent

    from zrb.llm.agent.common import create_safe_wrapper

    captured: list = []

    def probe(x: str) -> dict:
        raise ValueError(PAYLOAD)

    agent = Agent(_function_model(captured))
    agent.tool_plain(create_safe_wrapper(probe, name="probe"))

    result = await agent.run("go")

    assert _payload_occurrences(captured[-1]) == 1
    kinds = [
        [part.part_kind for part in message.parts] for message in result.all_messages()
    ]
    assert kinds == [["user-prompt"], ["tool-call"], ["tool-return"], ["text"]]


def test_tool_return_leaves_content_unset():
    """The helper is the single place the invariant is enforced."""
    from zrb.llm.agent.tool_result import tool_return

    built = tool_return("visible text", blocked=True)

    assert built.return_value == "visible text"
    assert built.content is None
    assert built.metadata == {"blocked": True}


def test_tool_return_without_metadata_is_an_empty_dict():
    """Callers inspect metadata unguarded, so it is never None."""
    from zrb.llm.agent.tool_result import tool_return

    assert tool_return("x").metadata == {}


@pytest.mark.asyncio
async def test_multimodal_result_survives_the_wrapper():
    """An image a tool returns must reach `return_value` intact.

    Providers extract multimodal parts out of `return_value`; any text rendering
    of one is a lossy repr, so a wrapper that stringifies drops the file the
    model was supposed to see (`files` goes 1 -> 0).
    """
    from pydantic_ai import BinaryContent
    from pydantic_ai.messages import ToolReturnPart

    from zrb.llm.agent.common import create_safe_wrapper

    image = BinaryContent(data=b"\x89PNG-BYTES", media_type="image/png")

    def screenshot() -> BinaryContent:
        return image

    result = await create_safe_wrapper(screenshot, name="screenshot")()
    part = ToolReturnPart(
        tool_name="screenshot", content=result.return_value, tool_call_id="1"
    )

    assert len(part.files) == 1
    assert part.files[0].media_type == "image/png"


@pytest.mark.asyncio
async def test_multimodal_inside_a_list_survives_the_wrapper():
    from pydantic_ai import BinaryContent
    from pydantic_ai.messages import ToolReturnPart

    from zrb.llm.agent.common import create_safe_wrapper

    image = BinaryContent(data=b"\x89PNG-BYTES", media_type="image/png")

    def mixed() -> list:
        return ["caption", image]

    result = await create_safe_wrapper(mixed, name="mixed")()
    part = ToolReturnPart(
        tool_name="mixed", content=result.return_value, tool_call_id="1"
    )

    assert len(part.files) == 1


@pytest.mark.asyncio
async def test_structured_result_stays_structured_for_google():
    """Google maps `return_value` via `model_response_object`.

    A dict passes through as the native functionResponse; a stringified copy
    would arrive wrapped as `{"return_value": "<escaped json>"}` instead.
    """
    from pydantic_ai.messages import ToolReturnPart

    from zrb.llm.agent.common import create_safe_wrapper

    def lookup() -> dict:
        return {"result": "abc", "n": 1}

    result = await create_safe_wrapper(lookup, name="lookup")()
    part = ToolReturnPart(
        tool_name="lookup", content=result.return_value, tool_call_id="1"
    )

    assert part.model_response_object() == {"result": "abc", "n": 1}
    assert part.structured_content() == {"result": "abc", "n": 1}


@pytest.mark.asyncio
async def test_oversized_result_is_flagged_but_not_rewritten():
    """The size cap never bounded what the model reads; removing the duplicate
    copy must not quietly change that."""
    from zrb.llm.agent.common import create_safe_wrapper

    big = {"k": "z" * 200_000}

    def huge() -> dict:
        return big

    result = await create_safe_wrapper(huge, name="huge")()

    assert result.return_value == big
    assert result.metadata.get("oversized") is True
