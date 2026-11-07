"Prompt hook — one of the two LLM-backed hook types (the other, the agent"

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.llm.shared.agent_state import is_current_run_nested
from zrb.llm.hook.creator import create_prompt_hook
from zrb.llm.hook.interface import HookContext, HookResult
from zrb.llm.hook.manager import HookManager
from zrb.llm.hook.schema import PromptHookConfig
from zrb.llm.hook.types import HookEvent


def _agent_returning(output):
    "Build a patchable pydantic_ai.Agent whose run() returns `output`."
    agent_instance = MagicMock()
    agent_instance.run = AsyncMock(return_value=MagicMock(output=output))
    agent_cls = MagicMock(return_value=agent_instance)
    return agent_cls


def _patched_agent(agent_cls):
    "Patch in *agent_cls* as pydantic_ai.Agent with a stub model resolver."
    return (
        patch("zrb.llm.hook.creator.resolve_configured_model"),
        patch.dict("sys.modules", {"pydantic_ai": MagicMock(Agent=agent_cls)}),
    )


@pytest.mark.asyncio
async def test_prompt_hook_no_model_configured():
    "With no model on the config and CFG.LLM_MODEL empty, the hook fails fast."
    config = PromptHookConfig(user_prompt_template="hi", model=None)
    hook = create_prompt_hook(config)
    context = HookContext(event=HookEvent.USER_PROMPT_SUBMIT, event_data={})

    with patch("zrb.llm.hook.creator.CFG") as mock_cfg:
        mock_cfg.LLM_MODEL = ""
        result = await hook(context)

    assert result.success is False
    assert "No LLM model" in (result.output or "")


@pytest.mark.asyncio
async def test_prompt_hook_plain_output_success():
    "A plain (non-JSON) agent output is returned with empty modifications, and"
    config = PromptHookConfig(
        user_prompt_template="Prompt was: {{prompt}}", model="fake-model"
    )
    hook = create_prompt_hook(config)
    context = HookContext(
        event=HookEvent.USER_PROMPT_SUBMIT, event_data={}, prompt="do it"
    )

    agent_cls = _agent_returning("plain answer")
    mock_config, mock_module = _patched_agent(agent_cls)
    with mock_config as mock_resolve_model, mock_module:
        mock_resolve_model.return_value = "resolved"
        result = await hook(context)

    assert result.success is True
    assert result.output == "plain answer"
    assert result.modifications == {}

    called_prompt = agent_cls.return_value.run.call_args.args[0]
    assert called_prompt == "Prompt was: do it"


@pytest.mark.asyncio
async def test_prompt_hook_json_output_becomes_modifications():
    "A JSON-object agent output is parsed into modifications."
    config = PromptHookConfig(user_prompt_template="x", model="fake-model")
    hook = create_prompt_hook(config)
    context = HookContext(event=HookEvent.USER_PROMPT_SUBMIT, event_data={})

    mock_config, mock_module = _patched_agent(_agent_returning('{"decision": "block"}'))
    with mock_config as mock_resolve_model, mock_module:
        mock_resolve_model.return_value = "resolved"
        result = await hook(context)

    assert result.success is True
    assert result.modifications == {"decision": "block"}


@pytest.mark.asyncio
async def test_prompt_hook_malformed_json_output_stays_plain():
    "Output that looks like JSON ({...}) but doesn't parse keeps empty"
    config = PromptHookConfig(user_prompt_template="x", model="fake-model")
    hook = create_prompt_hook(config)
    context = HookContext(event=HookEvent.USER_PROMPT_SUBMIT, event_data={})

    mock_config, mock_module = _patched_agent(_agent_returning("{not valid json}"))
    with mock_config as mock_resolve_model, mock_module:
        mock_resolve_model.return_value = "resolved"
        result = await hook(context)

    assert result.success is True
    assert result.modifications == {}


@pytest.mark.asyncio
async def test_prompt_hook_exception_returns_failure():
    "An error while running the agent is caught and returned as failure."
    config = PromptHookConfig(user_prompt_template="x", model="fake-model")
    hook = create_prompt_hook(config)
    context = HookContext(event=HookEvent.USER_PROMPT_SUBMIT, event_data={})

    mock_config, mock_module = _patched_agent(
        MagicMock(side_effect=RuntimeError("nope"))
    )
    with mock_config as mock_resolve_model, mock_module:
        mock_resolve_model.return_value = "resolved"
        result = await hook(context)

    assert result.success is False
    assert "nope" in (result.output or "")


@pytest.mark.asyncio
async def test_a_hooks_run_is_marked_nested_while_it_runs():
    "A hook's agent runs with no user waiting on it, so the events it fires are not"
    "the turn's. The mark says so for as long as it runs — that is what a listener"
    "reading the payload, or the ambient value, decides whether to paint from."
    config = PromptHookConfig(user_prompt_template="x", model="fake-model")
    hook = create_prompt_hook(config)
    context = HookContext(event=HookEvent.USER_PROMPT_SUBMIT, event_data={})

    manager = HookManager(search_dirs=[])
    payloads = []

    async def capture(hook_context):
        payloads.append(dict(hook_context.event_data))
        return HookResult()

    manager.add_hook(capture, events=[HookEvent.PRE_TOOL_USE])
    ambient = []

    async def run(prompt):
        ambient.append(is_current_run_nested())
        await manager.execute_hooks(HookEvent.PRE_TOOL_USE, {"tool": "Remember"})
        return MagicMock(output="ok")

    agent = MagicMock()
    agent.run = run
    with (
        patch("zrb.llm.hook.creator.create_agent", return_value=agent),
        patch("zrb.llm.hook.creator.resolve_configured_model", return_value="resolved"),
    ):
        result = await hook(context)

    assert result.success is True
    assert ambient == [True]
    assert payloads == [{"tool": "Remember", "nested_run": True}]
    assert is_current_run_nested() is False  # the mark ends with the run


@pytest.mark.asyncio
async def test_a_failed_hook_run_does_not_leave_the_mark_behind():
    "A mark that outlived its run would mute the face for the rest of the session."
    config = PromptHookConfig(user_prompt_template="x", model="fake-model")
    hook = create_prompt_hook(config)
    context = HookContext(event=HookEvent.USER_PROMPT_SUBMIT, event_data={})

    async def run(prompt):
        raise RuntimeError("boom")

    agent = MagicMock()
    agent.run = run
    with (
        patch("zrb.llm.hook.creator.create_agent", return_value=agent),
        patch("zrb.llm.hook.creator.resolve_configured_model", return_value="resolved"),
    ):
        result = await hook(context)

    assert result.success is False
    assert is_current_run_nested() is False
