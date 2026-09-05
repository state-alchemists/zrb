"""Tests for agent common utilities."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.config.config import CFG
from zrb.llm.agent.common import create_safe_wrapper


def _route_hooks(mapping):
    """An execute_hooks mock that returns per-event HookExecutionResult lists."""

    async def _execute(event, data, *args, **kwargs):
        return mapping.get(event, [])

    return AsyncMock(side_effect=_execute)


def _settings_of(mock_agent_class) -> dict:
    _, kwargs = mock_agent_class.call_args
    return kwargs.get("model_settings")


def _default_timeout() -> float:
    """The request deadline every agent carries, in seconds."""
    return CFG.LLM_REQUEST_TIMEOUT / 1000


def _reasoning_defaults() -> dict:
    """The reasoning/caching defaults every agent carries unless overridden."""
    return {
        "openai_reasoning_summary": "auto",
        "openai_prompt_cache_retention": "24h",
        "anthropic_cache": "5m",
    }


@pytest.mark.asyncio
async def test_call_tool_override_note_is_one_shot_and_reaches_error_results():
    """The note is consumed once per call, and still reaches the model when
    the (edited) call fails."""
    from pydantic_ai import ToolReturn
    from pydantic_ai.toolsets import FunctionToolset

    from zrb.llm.agent.common import wrap_toolset
    from zrb.llm.tool_call.override_registry import record_override

    wrapped_ts = wrap_toolset(FunctionToolset(tools=[]))
    record_override("edited-call-2", {"path": "a.txt"}, {"path": "b.txt"})
    ctx = MagicMock(tool_call_id="edited-call-2")
    with patch(
        "pydantic_ai.toolsets.WrapperToolset.call_tool",
        side_effect=ValueError("boom"),
    ):
        res = await wrapped_ts.call_tool("t", {"path": "b.txt"}, ctx, None)

    assert isinstance(res, ToolReturn)
    assert res.metadata.get("error") is True
    assert isinstance(res.return_value, str)
    assert "[SYSTEM NOTE]" in res.return_value

    # Second call for the same tool_call_id: nothing left to consume.
    with patch(
        "pydantic_ai.toolsets.WrapperToolset.call_tool", new_callable=AsyncMock
    ) as mock_super:
        mock_super.return_value = "ok"
        res2 = await wrapped_ts.call_tool("t", {"path": "b.txt"}, ctx, None)

    assert res2.return_value == "ok"


@pytest.mark.asyncio
async def test_call_tool_passes_claude_tool_identity_fields():
    """Pre/PostToolUse fire with Claude-standard tool_name/tool_input (and
    tool_response on Post) so tool-name matchers and stdin reads work."""
    from pydantic_ai.toolsets import FunctionToolset

    from zrb.llm.agent.common import wrap_toolset
    from zrb.llm.hook.types import HookEvent

    wrapped_ts = wrap_toolset(FunctionToolset(tools=[]))
    execute = _route_hooks({})
    with (
        patch("zrb.llm.hook.manager.hook_manager.execute_hooks", execute),
        patch(
            "pydantic_ai.toolsets.WrapperToolset.call_tool", new_callable=AsyncMock
        ) as mock_super,
    ):
        mock_super.return_value = "ok"
        await wrapped_ts.call_tool("Bash", {"command": "ls"}, None, None)

    pre = next(c for c in execute.call_args_list if c.args[0] == HookEvent.PRE_TOOL_USE)
    assert pre.kwargs["tool_name"] == "Bash"
    assert pre.kwargs["tool_input"] == {"command": "ls"}

    post = next(
        c for c in execute.call_args_list if c.args[0] == HookEvent.POST_TOOL_USE
    )
    assert post.kwargs["tool_name"] == "Bash"
    assert post.kwargs["tool_input"] == {"command": "ls"}
    # A plain-string tool result is wrapped under "content" for a JSON-safe payload.
    assert post.kwargs["tool_response"] == {"content": "ok"}


@pytest.mark.asyncio
async def test_posttooluse_failure_passes_claude_tool_identity_fields():
    """PostToolUseFailure carries tool_name/tool_input too."""
    from pydantic_ai.toolsets import FunctionToolset

    from zrb.llm.agent.common import wrap_toolset
    from zrb.llm.hook.types import HookEvent

    wrapped_ts = wrap_toolset(FunctionToolset(tools=[]))
    execute = _route_hooks({})
    with (
        patch("zrb.llm.hook.manager.hook_manager.execute_hooks", execute),
        patch(
            "pydantic_ai.toolsets.WrapperToolset.call_tool",
            side_effect=ValueError("boom"),
        ),
    ):
        await wrapped_ts.call_tool("Bash", {"command": "ls"}, None, None)

    fail = next(
        c
        for c in execute.call_args_list
        if c.args[0] == HookEvent.POST_TOOL_USE_FAILURE
    )
    assert fail.kwargs["tool_name"] == "Bash"
    assert fail.kwargs["tool_input"] == {"command": "ls"}


def test_create_agent_uses_default_model_when_none():
    """Test create_agent uses CFG.LLM_MODEL when model=None."""
    from unittest.mock import MagicMock, patch

    from zrb.llm.agent.common import create_agent

    mock_agent_class = MagicMock()

    with patch(
        "zrb.llm.agent.common.resolve_configured_model",
        return_value="default-model",
    ) as mock_resolve:
        with patch("pydantic_ai.Agent", mock_agent_class):
            try:
                create_agent(model=None, system_prompt="test", yolo=True)
            except Exception:
                pass  # May fail due to mocking

    # None falls back to CFG.LLM_MODEL before resolution.
    mock_resolve.assert_called_once_with(CFG.LLM_MODEL)


def test_create_agent_resolves_model_once_by_default():
    """With the default resolve_model=True, create_agent resolves the model
    (via resolve_configured_model) exactly once."""
    from unittest.mock import MagicMock, patch

    from zrb.llm.agent.common import create_agent

    with patch(
        "zrb.llm.agent.common.resolve_configured_model",
        return_value="resolved-model",
    ) as mock_resolve:
        with patch("pydantic_ai.Agent", MagicMock()):
            create_agent(model="base-model", system_prompt="test", yolo=True)

    mock_resolve.assert_called_once_with("base-model")


def test_create_agent_skips_resolution_when_resolve_model_false():
    """Resolve_model=False means the caller already resolved the model, so
    create_agent must NOT resolve it again (which would double-fire
    model_getter/model_renderer, potentially feeding a Model object into a
    getter that expects a tier string)."""
    from unittest.mock import MagicMock, patch

    from zrb.llm.agent.common import create_agent

    with patch("zrb.llm.agent.common.resolve_configured_model") as mock_resolve:
        with patch("pydantic_ai.Agent", MagicMock()) as mock_agent_class:
            create_agent(
                model="already-resolved",
                system_prompt="test",
                yolo=True,
                resolve_model=False,
            )

    mock_resolve.assert_not_called()
    # The pre-resolved model is passed straight through to the Agent.
    assert mock_agent_class.call_args.kwargs["model"] == "already-resolved"


def test_create_agent_with_callable_yolo():
    """Test create_agent with callable yolo."""
    from unittest.mock import MagicMock, patch

    from zrb.llm.agent.common import create_agent

    mock_agent_class = MagicMock()
    yolo_func = lambda ctx, tool, args: True  # Always approve

    with patch("pydantic_ai.Agent", mock_agent_class):
        try:
            create_agent(
                model="test-model",
                system_prompt="test",
                yolo=yolo_func,
            )
        except Exception:
            pass  # May fail due to mocking


def test_create_agent_retries_fallback():
    """Test create_agent correctly falls back to CFG.LLM_TOOL_MAX_RETRIES when retries is None."""
    from unittest.mock import MagicMock, patch

    from zrb.llm.agent.common import create_agent

    mock_agent_class = MagicMock()
    mock_config = MagicMock()
    mock_config.model = "default-model"

    with patch("zrb.llm.agent.common.CFG") as mock_cfg:
        mock_cfg.LLM_TOOL_MAX_RETRIES = 5
        # Stubbing the whole singleton means every field create_agent reads has
        # to be a real value, not a MagicMock — the request deadline is compared
        # numerically.
        mock_cfg.LLM_REQUEST_TIMEOUT = 300000
        with patch("pydantic_ai.Agent", mock_agent_class):

            # 1. retries=None (should use CFG.LLM_TOOL_MAX_RETRIES)
            create_agent(model="test-model", retries=None, yolo=True)
            args, kwargs = mock_agent_class.call_args
            assert kwargs.get("retries") == {"tools": 5}

            # 2. retries is specified (should override CFG)
            create_agent(model="test-model", retries=2, yolo=True)
            args, kwargs = mock_agent_class.call_args
            assert kwargs.get("retries") == {"tools": 2}


def test_create_agent_forces_sequential_for_parallel_unsupported_model():
    """Models in the capabilities deny-list get ``parallel_tool_calls=False``."""
    from zrb.llm.agent.common import create_agent

    mock_agent_class = MagicMock()
    with patch("pydantic_ai.Agent", mock_agent_class):
        create_agent(
            model="ollama:minimax-m2.7:cloud",
            system_prompt="test",
            yolo=True,
        )

    assert _settings_of(mock_agent_class) == {
        "parallel_tool_calls": False,
        "timeout": _default_timeout(),
        **_reasoning_defaults(),
    }


def test_create_agent_respects_caller_parallel_tool_calls_override():
    """Caller-supplied ``parallel_tool_calls`` is never overwritten."""
    from zrb.llm.agent.common import create_agent

    mock_agent_class = MagicMock()
    with patch("pydantic_ai.Agent", mock_agent_class):
        create_agent(
            model="ollama:minimax-m2.7:cloud",
            system_prompt="test",
            model_settings={"parallel_tool_calls": True, "temperature": 0.5},
            yolo=True,
        )

    assert _settings_of(mock_agent_class) == {
        "parallel_tool_calls": True,
        "temperature": 0.5,
        "timeout": _default_timeout(),
        **_reasoning_defaults(),
    }


def testcreate_safe_wrapper_preserves_function_name():
    """Test create_safe_wrapper preserves function name."""

    def my_func():
        pass

    wrapped = create_safe_wrapper(my_func)
    assert wrapped.__name__ == "my_func"
