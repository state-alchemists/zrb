"""Prompt hook — one of the two LLM-backed hook types (the other, the agent
hook, lives in `zrb.llm.agent.hook_agent` and is tested in
`test/llm/agent/test_hook_agent.py` — it needs the agent-building subsystem,
which `hook/creator.py` deliberately does not depend on).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.llm.hook.creator import create_prompt_hook
from zrb.llm.hook.interface import HookContext
from zrb.llm.hook.schema import PromptHookConfig
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
