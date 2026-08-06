"""Prompt and agent hooks — the two LLM-backed hook types.

Both go through the shared `_run_llm_hook` body, so the model-resolution and
JSON-output cases are exercised from each side.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.llm.hook.creator import create_agent_hook, create_prompt_hook
from zrb.llm.hook.interface import HookContext
from zrb.llm.hook.schema import AgentHookConfig, PromptHookConfig
from zrb.llm.hook.types import HookEvent


def _agent_returning(output):
    """Build a patchable pydantic_ai.Agent whose run() returns `output`."""
    agent_instance = MagicMock()
    agent_instance.run = AsyncMock(return_value=MagicMock(output=output))
    agent_cls = MagicMock(return_value=agent_instance)
    return agent_cls


def _patched_agent(agent_cls):
    """Patch in *agent_cls* as pydantic_ai.Agent with a stub model resolver."""
    return (
        patch("zrb.llm.hook.creator.llm_config"),
        patch.dict("sys.modules", {"pydantic_ai": MagicMock(Agent=agent_cls)}),
    )


# --- Prompt hook ---------------------------------------------------------


@pytest.mark.asyncio
async def test_prompt_hook_no_model_configured():
    """With no model on the config and CFG.LLM_MODEL empty, the hook fails fast."""
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
    """A plain (non-JSON) agent output is returned with empty modifications, and
    the user_prompt_template placeholders are substituted from context fields."""
    config = PromptHookConfig(
        user_prompt_template="Prompt was: {{prompt}}", model="fake-model"
    )
    hook = create_prompt_hook(config)
    context = HookContext(
        event=HookEvent.USER_PROMPT_SUBMIT, event_data={}, prompt="do it"
    )

    agent_cls = _agent_returning("plain answer")
    mock_config, mock_module = _patched_agent(agent_cls)
    with mock_config as mock_llm_config, mock_module:
        mock_llm_config.resolve_model.return_value = "resolved"
        result = await hook(context)

    assert result.success is True
    assert result.output == "plain answer"
    assert result.modifications == {}
    # Verify template substitution actually happened.
    called_prompt = agent_cls.return_value.run.call_args.args[0]
    assert called_prompt == "Prompt was: do it"


@pytest.mark.asyncio
async def test_prompt_hook_json_output_becomes_modifications():
    """A JSON-object agent output is parsed into modifications."""
    config = PromptHookConfig(user_prompt_template="x", model="fake-model")
    hook = create_prompt_hook(config)
    context = HookContext(event=HookEvent.USER_PROMPT_SUBMIT, event_data={})

    mock_config, mock_module = _patched_agent(_agent_returning('{"decision": "block"}'))
    with mock_config as mock_llm_config, mock_module:
        mock_llm_config.resolve_model.return_value = "resolved"
        result = await hook(context)

    assert result.success is True
    assert result.modifications == {"decision": "block"}


@pytest.mark.asyncio
async def test_prompt_hook_malformed_json_output_stays_plain():
    """Output that looks like JSON ({...}) but doesn't parse keeps empty
    modifications instead of raising."""
    config = PromptHookConfig(user_prompt_template="x", model="fake-model")
    hook = create_prompt_hook(config)
    context = HookContext(event=HookEvent.USER_PROMPT_SUBMIT, event_data={})

    mock_config, mock_module = _patched_agent(_agent_returning("{not valid json}"))
    with mock_config as mock_llm_config, mock_module:
        mock_llm_config.resolve_model.return_value = "resolved"
        result = await hook(context)

    assert result.success is True
    assert result.modifications == {}


@pytest.mark.asyncio
async def test_prompt_hook_exception_returns_failure():
    """An error while running the agent is caught and returned as failure."""
    config = PromptHookConfig(user_prompt_template="x", model="fake-model")
    hook = create_prompt_hook(config)
    context = HookContext(event=HookEvent.USER_PROMPT_SUBMIT, event_data={})

    mock_config, mock_module = _patched_agent(
        MagicMock(side_effect=RuntimeError("nope"))
    )
    with mock_config as mock_llm_config, mock_module:
        mock_llm_config.resolve_model.return_value = "resolved"
        result = await hook(context)

    assert result.success is False
    assert "nope" in (result.output or "")


# --- Agent hook ----------------------------------------------------------


@pytest.mark.asyncio
async def test_agent_hook_no_model_configured():
    config = AgentHookConfig(system_prompt="sp", model=None)
    hook = create_agent_hook(config)
    context = HookContext(event=HookEvent.NOTIFICATION, event_data={})

    with patch("zrb.llm.hook.creator.CFG") as mock_cfg:
        mock_cfg.LLM_MODEL = ""
        result = await hook(context)

    assert result.success is False
    assert "No LLM model" in (result.output or "")


@pytest.mark.asyncio
async def test_agent_hook_uses_dict_event_data_and_returns_json():
    """A dict event_data drives the agent input; a JSON output is parsed."""
    config = AgentHookConfig(system_prompt="sp", model="fake-model")
    hook = create_agent_hook(config)
    context = HookContext(event=HookEvent.NOTIFICATION, event_data={"a": 1})

    agent_cls = _agent_returning('{"ok": true}')
    mock_config, mock_module = _patched_agent(agent_cls)
    with mock_config as mock_llm_config, mock_module:
        mock_llm_config.resolve_model.return_value = "resolved"
        result = await hook(context)

    assert result.success is True
    assert result.modifications == {"ok": True}
    assert agent_cls.return_value.run.call_args.args[0] == "{'a': 1}"


@pytest.mark.asyncio
async def test_agent_hook_falls_back_to_event_value_when_no_input():
    """With no event_data and no prompt, the agent input is the event label."""
    config = AgentHookConfig(system_prompt="sp", model="fake-model")
    hook = create_agent_hook(config)
    context = HookContext(event=HookEvent.SESSION_START, event_data=None)

    agent_cls = _agent_returning("plain")
    mock_config, mock_module = _patched_agent(agent_cls)
    with mock_config as mock_llm_config, mock_module:
        mock_llm_config.resolve_model.return_value = "resolved"
        result = await hook(context)

    assert result.success is True
    assert result.modifications == {}
    user_input = agent_cls.return_value.run.call_args.args[0]
    assert HookEvent.SESSION_START.value in user_input


@pytest.mark.asyncio
async def test_agent_hook_uses_prompt_when_event_data_absent():
    """With no event_data but a prompt set, the prompt becomes the agent input."""
    config = AgentHookConfig(system_prompt="sp", model="fake-model")
    hook = create_agent_hook(config)
    context = HookContext(
        event=HookEvent.USER_PROMPT_SUBMIT, event_data=None, prompt="use me"
    )

    agent_cls = _agent_returning("plain")
    mock_config, mock_module = _patched_agent(agent_cls)
    with mock_config as mock_llm_config, mock_module:
        mock_llm_config.resolve_model.return_value = "resolved"
        await hook(context)

    assert agent_cls.return_value.run.call_args.args[0] == "use me"


@pytest.mark.asyncio
async def test_agent_hook_non_dict_event_data_stringified():
    """A non-dict, non-empty event_data is stringified for the agent input."""
    config = AgentHookConfig(system_prompt="sp", model="fake-model")
    hook = create_agent_hook(config)
    context = HookContext(event=HookEvent.NOTIFICATION, event_data="raw-text")

    agent_cls = _agent_returning("plain")
    mock_config, mock_module = _patched_agent(agent_cls)
    with mock_config as mock_llm_config, mock_module:
        mock_llm_config.resolve_model.return_value = "resolved"
        result = await hook(context)

    assert result.success is True
    assert agent_cls.return_value.run.call_args.args[0] == "raw-text"


@pytest.mark.asyncio
async def test_agent_hook_malformed_json_output_stays_plain():
    """Agent output that looks like JSON but doesn't parse keeps empty
    modifications."""
    config = AgentHookConfig(system_prompt="sp", model="fake-model")
    hook = create_agent_hook(config)
    context = HookContext(event=HookEvent.NOTIFICATION, event_data={"a": 1})

    mock_config, mock_module = _patched_agent(_agent_returning("{bad json}"))
    with mock_config as mock_llm_config, mock_module:
        mock_llm_config.resolve_model.return_value = "resolved"
        result = await hook(context)

    assert result.success is True
    assert result.modifications == {}


@pytest.mark.asyncio
async def test_agent_hook_exception_returns_failure():
    config = AgentHookConfig(system_prompt="sp", model="fake-model")
    hook = create_agent_hook(config)
    context = HookContext(event=HookEvent.NOTIFICATION, event_data={"a": 1})

    mock_config, mock_module = _patched_agent(
        MagicMock(side_effect=RuntimeError("boom"))
    )
    with mock_config as mock_llm_config, mock_module:
        mock_llm_config.resolve_model.return_value = "resolved"
        result = await hook(context)

    assert result.success is False
    assert "boom" in (result.output or "")
