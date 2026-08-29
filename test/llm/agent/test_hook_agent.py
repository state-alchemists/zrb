"""Agent hook — the one hook type implemented as a real sub-agent turn, so it
lives in `zrb.llm.agent.hook_agent` rather than `zrb.llm.hook.creator` (which
builds command/prompt hooks, neither of which needs the agent-building
subsystem). It still shares `run_llm_hook`'s model-resolution and JSON-output
handling with the prompt hook — see `test/llm/hook/test_creator_llm.py` for
that shared body's own tests, which is why some patches below still target
`zrb.llm.hook.creator` (where `run_llm_hook`, `CFG`, and `llm_config` live).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.llm.agent.hook_agent import create_agent_hook
from zrb.llm.hook.interface import HookContext
from zrb.llm.hook.schema import AgentHookConfig
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
async def test_agent_hook_skips_llm_call_when_no_named_tools_resolve():
    """When every tool the config names fails to resolve (e.g. the journal
    tools while LLM_JOURNAL_ENABLED is off), the hook must not spend an LLM
    call it cannot do anything useful with."""
    config = AgentHookConfig(
        system_prompt="sp", model="fake-model", tools=["LogActivity"]
    )
    hook = create_agent_hook(config)
    context = HookContext(event=HookEvent.STOP, event_data={"wrote_files": True})

    agent_cls = _agent_returning("should never run")
    mock_config, mock_module = _patched_agent(agent_cls)
    with (
        patch("zrb.llm.agent.hook_agent.ensure_common_tools"),
        patch(
            "zrb.llm.agent.subagent.manager.sub_agent_manager.get_tool_registry",
            return_value={},
        ),
        patch(
            "zrb.llm.agent.subagent.manager.sub_agent_manager.get_tool_factories",
            return_value=(),
        ),
        mock_config,
        mock_module,
    ):
        result = await hook(context)

    assert result.success is True
    assert "Skipped" in (result.output or "")
    agent_cls.assert_not_called()


@pytest.mark.asyncio
async def test_resolved_agent_hook_tools_contain_tool_errors():
    """A resolved tool's `[SYSTEM SUGGESTION]` ValueError (journal_write's link
    check is one real example) must come back as a tool result the judge
    model can react to, not an exception that aborts the whole hook run —
    the same containment `create_agent()` gives every other agent's tools."""
    from zrb.llm.agent.hook_agent import resolve_agent_hook_tools

    def flaky_tool() -> str:
        raise ValueError("[SYSTEM SUGGESTION]: link target does not exist.")

    flaky_tool.__name__ = "FlakyTool"

    with (
        patch("zrb.llm.agent.hook_agent.ensure_common_tools"),
        patch(
            "zrb.llm.agent.subagent.manager.sub_agent_manager.get_tool_registry",
            return_value={"FlakyTool": flaky_tool},
        ),
        patch(
            "zrb.llm.agent.subagent.manager.sub_agent_manager.get_tool_factories",
            return_value=(),
        ),
    ):
        resolved = resolve_agent_hook_tools(["FlakyTool"])

    assert len(resolved) == 1
    result = await resolved[0].function()
    assert result.metadata.get("error") is True
    assert "does not exist" in result.return_value


@pytest.mark.asyncio
async def test_agent_hook_runs_when_named_tools_do_resolve():
    """The opposite of the skip case: a resolved tool list reaches the agent."""
    config = AgentHookConfig(
        system_prompt="sp", model="fake-model", tools=["LogActivity"]
    )
    hook = create_agent_hook(config)
    context = HookContext(event=HookEvent.STOP, event_data={"wrote_files": True})

    def fake_log_activity(note: str) -> str:
        return f"logged: {note}"

    fake_log_activity.__name__ = "LogActivity"

    agent_cls = _agent_returning("logged")
    with (
        patch("zrb.llm.hook.creator.llm_config") as mock_llm_config,
        # Only Agent is swapped (unlike _patched_agent, which replaces the
        # whole pydantic_ai module) — this test inspects the real Tool that
        # wrap_tool builds around the resolved tool, below.
        patch("pydantic_ai.Agent", agent_cls),
        patch("zrb.llm.agent.hook_agent.ensure_common_tools"),
        patch(
            "zrb.llm.agent.subagent.manager.sub_agent_manager.get_tool_registry",
            return_value={"LogActivity": fake_log_activity},
        ),
        patch(
            "zrb.llm.agent.subagent.manager.sub_agent_manager.get_tool_factories",
            return_value=(),
        ),
    ):
        mock_llm_config.resolve_model.return_value = "resolved"
        result = await hook(context)

    assert result.success is True
    tools_passed = agent_cls.call_args.kwargs["tools"]
    assert len(tools_passed) == 1
    returned = await tools_passed[0].function(note="x")
    assert returned.return_value == "logged: x"


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
