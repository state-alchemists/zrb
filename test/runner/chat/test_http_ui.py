import asyncio
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from zrb.runner.chat.http_ui import create_http_ui_factory


@pytest.fixture
def mock_deps():
    session_manager = MagicMock()
    session_manager.broadcast = AsyncMock()
    approval_channel = MagicMock()

    factory = create_http_ui_factory(
        session_manager=session_manager,
        session_id="test-id",
        session_name="test-session",
        approval_channel=approval_channel,
    )

    ctx = MagicMock()
    llm_task = MagicMock()
    history_manager = MagicMock()

    ui = factory(
        ctx=ctx,
        llm_task=llm_task,
        history_manager=history_manager,
        ui_commands=None,
        initial_message=None,
        initial_conversation_name=None,
        initial_yolo=False,
        initial_attachments=None,
    )

    return ui, session_manager, approval_channel


@pytest.mark.asyncio
async def test_http_ui_print_and_input(mock_deps):
    ui, session_manager, _ = mock_deps

    # Test print text (public API)
    await ui.print("hello", kind="text")
    session_manager.broadcast.assert_called_with("test-id", "hello", kind="text")

    # Test input lifecycle using public methods
    ui.handle_incoming_message("user input")
    res = await ui.get_input("Please enter:")

    assert res == "user input"
    session_manager.broadcast.assert_any_call("test-id", "❓ Please enter:")


@pytest.mark.asyncio
async def test_http_ui_confirm_tool_execution(mock_deps):
    ui, _, approval_channel = mock_deps

    mock_call = MagicMock()
    mock_call.tool_name = "test_tool"
    mock_call.args = {"key": "val"}
    mock_call.tool_call_id = "123"

    channel_result = MagicMock()
    channel_result.to_pydantic_result.return_value = "Approved"
    approval_channel.request_approval = AsyncMock(return_value=channel_result)

    # _confirm_tool_execution is part of the UI protocol for tool use
    res = await ui._confirm_tool_execution(mock_call)

    assert res == "Approved"
    approval_channel.request_approval.assert_called_once()


@pytest.mark.asyncio
async def test_http_ui_run_async_logic(mock_deps):
    ui, _, _ = mock_deps
    # last_output is public
    with patch(
        "zrb.llm.ui.base.ui.BaseUI.last_output", new_callable=PropertyMock
    ) as mock_last:
        mock_last.return_value = "Done"
        res = await ui.run_async()
        assert res == "Done"


def test_create_http_ui_factory_with_commands():
    session_manager = MagicMock()
    approval_channel = MagicMock()
    factory = create_http_ui_factory(
        session_manager, "id", "test-session", approval_channel
    )

    ui_commands = {"exit": ["/leave"]}

    ui = factory(
        ctx=MagicMock(),
        llm_task=MagicMock(),
        history_manager=MagicMock(),
        ui_commands=ui_commands,
        initial_message=None,
        initial_conversation_name=None,
        initial_yolo=True,
        initial_attachments=None,
    )

    # Check public yolo and commands indirectly if possible,
    # but at least check that the factory returned a UI
    assert ui is not None
