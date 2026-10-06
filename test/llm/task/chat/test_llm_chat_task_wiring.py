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


@pytest.mark.asyncio
async def test_llm_chat_task_judges_an_arg_pattern_rule_with_the_calls_arguments():
    """The chat path's dynamic yolo hands the call's arguments to the policy,
    so an `arg_pattern` ASK is not auto-approved under yolo."""
    from zrb.llm.permission import ASK, PermissionPolicy, Rule
    from zrb.llm.permission.state import permission_policy

    policy = PermissionPolicy((Rule("Bash", ASK, arg_pattern="rm -rf*"),))
    task = LLMChatTask(
        name="arg-pattern-task",
        message="Hello",
        permissions=policy,
        yolo=True,
        interactive=False,
    )
    captured: dict = {}

    def capture_create_agent(**kwargs):
        captured.update(kwargs)
        return MagicMock()

    with (
        patch("zrb.llm.task.llm_task.create_agent", side_effect=capture_create_agent),
        patch(
            "zrb.llm.task.llm_task.run_agent", new_callable=AsyncMock
        ) as mock_run_agent,
    ):
        mock_run_agent.return_value = ("Done", [])
        session = Session(SharedContext(), state_logger=MagicMock())
        await task.async_run(session)

    decide = captured["yolo"]
    tool_def = MagicMock()
    tool_def.name = "Bash"
    # `run_agent` binds the policy in a real run; it is patched here.
    with permission_policy(policy):
        # The rule matches: a hard ask, even under YOLO.
        assert decide(tool_def, {"command": "rm -rf /tmp/x"}) is False
        # The pattern does not match, so YOLO covers it.
        assert decide(tool_def, {"command": "ls -la"}) is True


@pytest.mark.asyncio
async def test_llm_chat_task_forwards_stream_observers_to_run_agent():
    observer = MagicMock()
    task = LLMChatTask(name="observer-task", message="Hello", interactive=False)
    task.append_stream_observer(observer)

    with patch(
        "zrb.llm.task.llm_task.run_agent", new_callable=AsyncMock
    ) as mock_run_agent:
        mock_run_agent.return_value = ("Done", [])
        session = Session(SharedContext(), state_logger=MagicMock())
        await task.async_run(session)

    assert mock_run_agent.call_args.kwargs["stream_observers"] == [observer]


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
    """A one-shot run drains its detached hooks before returning."""
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
    """The inner LLMTask does not add retries on top of the chat task's."""
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
    """A 429 is retried: 3 attempts for retries=2, with no inner-task retries."""
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


@pytest.mark.asyncio
async def test_the_inner_task_runs_with_the_chats_active_hook_manager():
    """The UI holds the inner LLMTask; cancelling a turn fires Stop on its
    `hook_manager`, which must be the manager the turn's hooks live on."""
    task = LLMChatTask(name="hook-task", message="Hello", interactive=False)

    with patch(
        "zrb.llm.task.llm_task.run_agent", new_callable=AsyncMock
    ) as mock_run_agent:
        mock_run_agent.return_value = ("Done", [])
        await task.async_run(Session(SharedContext(), state_logger=MagicMock()))

    used = mock_run_agent.call_args.kwargs["hook_manager"]
    assert used is task.active_hook_manager
