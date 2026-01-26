from unittest.mock import AsyncMock, patch

import pytest
from pydantic_ai import ToolApproved

from zrb.context.shared_context import SharedContext
from zrb.llm.task.llm_task import LLMTask
from zrb.session.session import Session


@pytest.mark.asyncio
async def test_llm_task_tool_confirmation_called():
    # Mock create_agent and run_agent in the module where LLMTask is defined
    with patch("zrb.llm.task.llm_task.create_agent") as mock_create_agent, patch(
        "zrb.llm.task.llm_task.run_agent", new_callable=AsyncMock
    ) as mock_run_agent:

        mock_create_agent.return_value = "mock_agent"
        mock_run_agent.return_value = ("Done", [])

        def tool_confirmation(call):
            return ToolApproved()

        mock_history_manager = patch(
            "zrb.llm.history_manager.any_history_manager.AnyHistoryManager"
        ).start()
        mock_history_manager.load.return_value = []

        task = LLMTask(
            name="test-task",
            message="Hello",
            tool_confirmation=tool_confirmation,
            history_manager=mock_history_manager,
            yolo=False,
        )

        shared_ctx = SharedContext()
        session = Session(shared_ctx)

        # Execute
        await task.async_run(session)

        # Assert
        mock_run_agent.assert_called_once()
        args, kwargs = mock_run_agent.call_args
        assert kwargs["tool_confirmation"] == tool_confirmation


@pytest.mark.asyncio
async def test_llm_chat_task_tool_confirmation_forwarded():
    from zrb.context.shared_context import SharedContext
    from zrb.llm.task.llm_chat_task import LLMChatTask
    from zrb.session.session import Session

    def tool_confirmation(call):
        return ToolApproved()

    chat_task = LLMChatTask(
        name="chat-task",
        tool_confirmation=tool_confirmation,
        interactive=False,  # So we use the core task
    )

    # Create a mock context
    shared_ctx = SharedContext()
    session = Session(shared_ctx)

    # We want to check if the core task has the tool_confirmation
    mock_history_manager = patch(
        "zrb.llm.history_manager.any_history_manager.AnyHistoryManager"
    ).start()
    core_task = chat_task._create_llm_task_core(
        session, [], mock_history_manager, interactive=False
    )
    assert core_task._tool_confirmation == tool_confirmation


@pytest.mark.asyncio
async def test_llm_chat_task_interactive_handler_wrapping():
    from zrb.context.shared_context import SharedContext
    from zrb.llm.task.llm_chat_task import LLMChatTask
    from zrb.llm.tool_call import ToolCallHandler
    from zrb.session.session import Session

    async def my_handler(ui, call, response, next_handler):
        return await next_handler(ui, call, response)

    chat_task = LLMChatTask(
        name="chat-task",
        response_handlers=[my_handler],
        interactive=True,
    )

    # Create a mock context
    shared_ctx = SharedContext()
    session = Session(shared_ctx)

    # Interactive=True: Should set tool_confirmation to None (defer to UI context var)
    mock_history_manager = patch(
        "zrb.llm.history_manager.any_history_manager.AnyHistoryManager"
    ).start()
    core_task_interactive = chat_task._create_llm_task_core(
        session, [], mock_history_manager, interactive=True
    )
    assert core_task_interactive._tool_confirmation is None

    # Interactive=False: Should NOT wrap (since handlers are filtered out and policies are empty)
    core_task_non_interactive = chat_task._create_llm_task_core(
        session, [], mock_history_manager, interactive=False
    )
    assert not isinstance(core_task_non_interactive._tool_confirmation, ToolCallHandler)


@pytest.mark.asyncio
async def test_llm_chat_task_policy_wrapping():
    from zrb.context.shared_context import SharedContext
    from zrb.llm.task.llm_chat_task import LLMChatTask
    from zrb.llm.tool_call import ToolCallHandler
    from zrb.session.session import Session

    async def my_policy(call, next_handler):
        return await next_handler(call)

    chat_task = LLMChatTask(
        name="policy-task",
        tool_policies=[my_policy],
        interactive=False,
    )

    # Create a mock context
    shared_ctx = SharedContext()
    session = Session(shared_ctx)

    # Interactive=False with policies: Should get a simple callable wrapper, NOT ToolCallHandler
    mock_history_manager = patch(
        "zrb.llm.history_manager.any_history_manager.AnyHistoryManager"
    ).start()
    core_task = chat_task._create_llm_task_core(
        session, [], mock_history_manager, interactive=False
    )
    assert callable(core_task._tool_confirmation)
    assert not isinstance(core_task._tool_confirmation, ToolCallHandler)
