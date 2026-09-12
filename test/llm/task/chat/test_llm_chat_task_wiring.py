from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.context.shared_context import SharedContext
from zrb.llm.history_manager.any_history_manager import AnyHistoryManager
from zrb.llm.task.chat.task import LLMChatTask
from zrb.session.session import Session


@pytest.mark.asyncio
async def test_llm_chat_task_passes_getter_renderer_to_summarizer():
    """LLMChatTask forwards its model_getter/model_renderer to create_summarizer_history_processor."""
    getter = lambda m: "getter-model"
    renderer = lambda m: "renderer-model"

    task = LLMChatTask(
        name="test-task",
        model_getter=getter,
        model_renderer=renderer,
        interactive=False,
    )

    with (
        patch(
            "zrb.llm.task.chat.execution.create_summarizer_history_processor"
        ) as mock_create_proc,
        patch("zrb.llm.task.llm_task.create_agent"),
        patch(
            "zrb.llm.task.llm_task.run_agent", new_callable=AsyncMock
        ) as mock_run_agent,
    ):
        mock_proc = MagicMock()
        mock_proc.return_value = AsyncMock(return_value=[])
        mock_create_proc.return_value = mock_proc
        mock_run_agent.return_value = ("Done", [])

        shared_ctx = SharedContext()
        session = Session(shared_ctx, state_logger=MagicMock())
        await task.async_run(session)

    mock_create_proc.assert_called_once()


def test_llm_chat_task_permissions_constructor_and_property():
    from zrb.llm.permission import ALLOW, PermissionPolicy, Rule

    policy = PermissionPolicy((Rule("*", ALLOW),))
    task = LLMChatTask(name="test-task", permissions=policy)
    assert task.permissions is policy


def test_llm_chat_task_permissions_setter():
    from zrb.llm.permission import DENY, PermissionPolicy, Rule

    policy = PermissionPolicy((Rule("*", DENY),))
    task = LLMChatTask(name="test-task")
    assert task.permissions is None
    task.permissions = policy
    assert task.permissions is policy


@pytest.mark.asyncio
async def test_llm_chat_task_forwards_permissions_to_run_agent():
    """The permissions policy reaches run_agent as permission_policy."""
    from zrb.llm.permission import ASK, PermissionPolicy, Rule

    policy = PermissionPolicy((Rule("Edit", ASK), Rule("*", ASK)))
    task = LLMChatTask(
        name="perm-forward-task",
        message="Hello",
        permissions=policy,
        interactive=False,
    )

    with patch(
        "zrb.llm.task.llm_task.run_agent", new_callable=AsyncMock
    ) as mock_run_agent:
        mock_run_agent.return_value = ("Done", [])

        shared_ctx = SharedContext()
        session = Session(shared_ctx, state_logger=MagicMock())
        await task.async_run(session)

    assert mock_run_agent.called
    assert mock_run_agent.call_args.kwargs["permission_policy"] is policy


def test_llm_chat_task_history_config_reflects_constructor_values():
    manager = MagicMock()
    task = LLMChatTask(
        name="test-task",
        history_manager=manager,
        conversation_name="my-convo",
    )
    config = task.history_config
    assert config.history_manager is manager
    assert config.conversation_name == "my-convo"


def test_llm_chat_task_history_config_reflects_history_manager_setter_immediately():
    task = LLMChatTask(name="test-task")
    new_manager = MagicMock(spec=AnyHistoryManager)
    task.history_manager = new_manager
    assert task.history_config.history_manager is new_manager


def test_llm_chat_task_history_manager_setter_rejects_wrong_type():
    task = LLMChatTask(name="test-task")
    with pytest.raises(TypeError, match="AnyHistoryManager"):
        task.history_manager = "not a manager"


def test_llm_chat_task_sandbox_constructor_and_property():
    from zrb.llm.sandbox import SandboxPolicy

    policy = SandboxPolicy(enabled=True)
    task = LLMChatTask(name="test-task", sandbox=policy)
    assert task.sandbox is policy


def test_llm_chat_task_sandbox_setter():
    from zrb.llm.sandbox import SandboxPolicy

    policy = SandboxPolicy(enabled=True)
    task = LLMChatTask(name="test-task")
    assert task.sandbox is None
    task.sandbox = policy
    assert task.sandbox is policy


@pytest.mark.asyncio
async def test_llm_chat_task_forwards_sandbox_to_run_agent():
    """The sandbox policy reaches run_agent as sandbox_policy."""
    from zrb.llm.sandbox import SandboxPolicy

    policy = SandboxPolicy(enabled=True)
    task = LLMChatTask(
        name="sandbox-forward-task",
        message="Hello",
        sandbox=policy,
        interactive=False,
    )

    with patch(
        "zrb.llm.task.llm_task.run_agent", new_callable=AsyncMock
    ) as mock_run_agent:
        mock_run_agent.return_value = ("Done", [])

        shared_ctx = SharedContext()
        session = Session(shared_ctx, state_logger=MagicMock())
        await task.async_run(session)

    assert mock_run_agent.called
    assert mock_run_agent.call_args.kwargs["sandbox_policy"] is policy


@pytest.mark.asyncio
async def test_non_interactive_run_settles_its_background_hooks():
    """A one-shot run must not leave detached hooks running after it returns.

    Regression: only the interactive path had a teardown, so `zrb llm chat -m
    "..."` and the web/SSE runner left their `async: true` hooks alive — they sit
    in their own process group, so nothing else reaps them. Drained rather than
    cancelled up front: this fires at *run* end, possibly moments after the hook
    was dispatched.
    """
    from zrb.llm.hook.manager import HookManager

    with (
        patch(
            "zrb.llm.task.llm_task.run_agent", new_callable=AsyncMock
        ) as mock_run_agent,
        patch.object(HookManager, "shutdown", new_callable=AsyncMock) as mock_shutdown,
    ):
        mock_run_agent.return_value = ("AI response", [])
        task = LLMChatTask(
            name="non-interactive-hook-teardown", message="Hi", interactive=False
        )
        await task.async_run(Session(SharedContext(), state_logger=MagicMock()))

    mock_shutdown.assert_awaited_once_with(drain=True)


@pytest.mark.asyncio
async def test_chat_task_with_no_retries_calls_the_agent_once():
    """The inner LLMTask used to default to 2 retries of its own, multiplying
    against the outer chat task's -- so retries=0 still ran the agent 3 times."""
    from pydantic_ai.exceptions import UserError

    task = LLMChatTask(name="test-task", interactive=False)
    assert task.retries == 0

    with (
        patch("zrb.llm.task.llm_task.create_agent"),
        patch(
            "zrb.llm.task.llm_task.run_agent", new_callable=AsyncMock
        ) as mock_run_agent,
    ):
        mock_run_agent.side_effect = UserError("Set the `OPENAI_API_KEY` env var")
        session = Session(SharedContext(), state_logger=MagicMock())
        with pytest.raises(UserError):
            await task.async_run(session)

    assert mock_run_agent.call_count == 1


@pytest.mark.asyncio
async def test_permanent_error_is_not_retried_even_when_retries_allowed():
    """retries=2 still means one attempt when the failure cannot succeed."""
    from pydantic_ai.exceptions import UserError

    task = LLMChatTask(name="test-task", interactive=False, retries=2)

    with (
        patch("zrb.llm.task.llm_task.create_agent"),
        patch(
            "zrb.llm.task.llm_task.run_agent", new_callable=AsyncMock
        ) as mock_run_agent,
    ):
        mock_run_agent.side_effect = UserError("Set the `OPENAI_API_KEY` env var")
        session = Session(SharedContext(), state_logger=MagicMock())
        with pytest.raises(UserError):
            await task.async_run(session)

    assert mock_run_agent.call_count == 1


@pytest.mark.asyncio
async def test_transient_error_still_burns_every_retry():
    """A 429 is exactly what retries exist for -- the gate must not eat it.

    3 attempts, not 9: the inner per-turn LLMTask no longer retries on top of
    the outer chat task's own retry loop.
    """
    task = LLMChatTask(name="test-task", interactive=False, retries=2)
    rate_limited = Exception("slow down")
    rate_limited.status_code = 429

    with (
        patch("zrb.llm.task.llm_task.create_agent"),
        patch(
            "zrb.llm.task.llm_task.run_agent", new_callable=AsyncMock
        ) as mock_run_agent,
    ):
        mock_run_agent.side_effect = rate_limited
        session = Session(SharedContext(), state_logger=MagicMock())
        with pytest.raises(Exception):
            await task.async_run(session)

    assert mock_run_agent.call_count == 3
