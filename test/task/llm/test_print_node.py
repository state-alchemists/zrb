from unittest.mock import MagicMock, call, patch

import pytest

from zrb.task.llm.print_node import print_node


@pytest.fixture
def mock_print():
    return MagicMock()


@pytest.fixture
def mock_agent_run():
    run = MagicMock()
    run.ctx = MagicMock()
    return run


@pytest.fixture
def mock_node():
    node = MagicMock()

    async def empty_async_iterator():
        if False:
            yield

    node.stream.return_value.__aenter__.return_value = empty_async_iterator()
    return node


# Mock events classes
class MockPartDeltaEvent:
    def __init__(self, delta):
        self.delta = delta


class MockTextPartDelta:
    def __init__(self, content_delta):
        self.content_delta = content_delta


class MockThinkingPartDelta:
    def __init__(self, content_delta):
        self.content_delta = content_delta


class MockToolCallPartDelta:
    def __init__(self, args_delta):
        self.args_delta = args_delta


class MockPartStartEvent:
    def __init__(self, part):
        self.part = part


class MockFinalResultEvent:
    def __init__(self, tool_name):
        self.tool_name = tool_name


class MockFunctionToolCallEvent:
    def __init__(self, part):
        self.part = part


class MockFunctionToolResultEvent:
    def __init__(self, tool_call_id, result):
        self.tool_call_id = tool_call_id
        self.result = result


@pytest.mark.asyncio
async def test_print_user_prompt_node(mock_print, mock_agent_run, mock_node):
    with patch("pydantic_ai.Agent.is_user_prompt_node", return_value=True):
        await print_node(mock_print, mock_agent_run, mock_node, is_tty=True)
        mock_print.assert_called()
        assert "Receiving input" in mock_print.call_args[0][0]


@pytest.mark.asyncio
async def test_print_end_node(mock_print, mock_agent_run, mock_node):
    with patch("pydantic_ai.Agent.is_user_prompt_node", return_value=False), patch(
        "pydantic_ai.Agent.is_model_request_node", return_value=False
    ), patch("pydantic_ai.Agent.is_call_tools_node", return_value=False), patch(
        "pydantic_ai.Agent.is_end_node", return_value=True
    ):

        await print_node(mock_print, mock_agent_run, mock_node, is_tty=True)
        assert "Completed" in mock_print.call_args[0][0]


@pytest.mark.asyncio
async def test_print_model_request_node_text_stream(
    mock_print, mock_agent_run, mock_node
):
    # Setup stream events
    events = [
        MockPartStartEvent(part=MagicMock(content="Start")),
        MockPartDeltaEvent(delta=MockTextPartDelta("Hello")),
        MockPartDeltaEvent(delta=MockTextPartDelta(" World")),
    ]

    async def event_generator():
        for e in events:
            yield e

    mock_node.stream.return_value.__aenter__.return_value = event_generator()

    with patch("pydantic_ai.Agent.is_user_prompt_node", return_value=False), patch(
        "pydantic_ai.Agent.is_model_request_node", return_value=True
    ), patch("pydantic_ai.messages.PartStartEvent", MockPartStartEvent), patch(
        "pydantic_ai.messages.PartDeltaEvent", MockPartDeltaEvent
    ), patch(
        "pydantic_ai.messages.TextPartDelta", MockTextPartDelta
    ):

        await print_node(mock_print, mock_agent_run, mock_node, is_tty=True)

        # Verify calls
        # Header
        assert "Processing" in mock_print.call_args_list[0][0][0]
        # Content calls
        calls = [str(c[0][0]) for c in mock_print.call_args_list]
        assert any("Start" in c for c in calls)
        assert any("Hello" in c for c in calls)
        assert any("World" in c for c in calls)


@pytest.mark.asyncio
async def test_print_model_request_node_tool_call_stream(
    mock_print, mock_agent_run, mock_node
):
    events = [
        MockPartDeltaEvent(delta=MockToolCallPartDelta(args_delta="arg")),
        MockPartDeltaEvent(delta=MockToolCallPartDelta(args_delta="s")),
    ]

    async def event_generator():
        for e in events:
            yield e

    mock_node.stream.return_value.__aenter__.return_value = event_generator()

    with patch("pydantic_ai.Agent.is_user_prompt_node", return_value=False), patch(
        "pydantic_ai.Agent.is_model_request_node", return_value=True
    ), patch("pydantic_ai.messages.PartDeltaEvent", MockPartDeltaEvent), patch(
        "pydantic_ai.messages.ToolCallPartDelta", MockToolCallPartDelta
    ), patch(
        "pydantic_ai.messages.TextPartDelta", MockTextPartDelta
    ), patch(
        "pydantic_ai.messages.ThinkingPartDelta", MockThinkingPartDelta
    ), patch(
        "zrb.task.llm.print_node.CFG"
    ) as mock_cfg:

        mock_cfg.LLM_SHOW_TOOL_CALL_PREPARATION = False

        await print_node(mock_print, mock_agent_run, mock_node, is_tty=True)

        # Should print progress spinner
        calls = [str(c[0][0]) for c in mock_print.call_args_list if len(c[0]) > 0]
        assert any("Preparing Tool Parameters" in c for c in calls)


@pytest.mark.asyncio
async def test_print_call_tools_node(mock_print, mock_agent_run, mock_node):
    part_mock = MagicMock()
    part_mock.tool_call_id = "call_1"
    part_mock.tool_name = "my_tool"
    part_mock.args = '{"a": 1}'

    events = [
        MockFunctionToolCallEvent(part=part_mock),
        MockFunctionToolResultEvent(
            tool_call_id="call_1", result=MagicMock(content="Result")
        ),
    ]

    async def event_generator():
        for e in events:
            yield e

    mock_node.stream.return_value.__aenter__.return_value = event_generator()

    with patch("pydantic_ai.Agent.is_user_prompt_node", return_value=False), patch(
        "pydantic_ai.Agent.is_model_request_node", return_value=False
    ), patch("pydantic_ai.Agent.is_call_tools_node", return_value=True), patch(
        "pydantic_ai.messages.FunctionToolCallEvent", MockFunctionToolCallEvent
    ), patch(
        "pydantic_ai.messages.FunctionToolResultEvent", MockFunctionToolResultEvent
    ), patch(
        "zrb.task.llm.print_node.CFG"
    ) as mock_cfg:

        mock_cfg.LLM_SHOW_TOOL_CALL_RESULT = True

        await print_node(mock_print, mock_agent_run, mock_node, is_tty=True)

        calls = [str(c[0][0]) for c in mock_print.call_args_list if len(c[0]) > 0]
        assert any("Calling Tool" in c for c in calls)
        assert any("my_tool" in c for c in calls)
        assert any("Result" in c for c in calls)
