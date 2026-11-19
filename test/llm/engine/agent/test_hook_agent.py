"""Agent hook — the one hook type implemented as a real sub-agent turn, so it
lives in `zrb.llm.engine.agent.hook_agent` rather than `zrb.llm.capabilities.hook.execution.creator` (which
builds command/prompt hooks, neither of which needs the agent-building
subsystem). It still shares `run_llm_hook`'s model-resolution and JSON-output
handling with the prompt hook — see `test/llm/capabilities/hook/test_creator_llm.py` for
that shared body's own tests, which is why some patches below still target
`zrb.llm.capabilities.hook.execution.creator` (where `run_llm_hook`, `CFG`, and `resolve_configured_model` live).
"""

import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic_ai import RunContext

from zrb.llm.capabilities.hook.contracts.interface import HookContext
from zrb.llm.capabilities.hook.contracts.schema import AgentHookConfig
from zrb.llm.capabilities.hook.contracts.types import HookEvent
from zrb.llm.contracts.shared.tool_registry import tool_registry
from zrb.llm.contracts.shared.tool_resolver import resolved_tool_name
from zrb.llm.engine.agent.hook_agent import create_agent_hook, resolve_agent_hook_tools


def _agent_returning(output):
    """Build a patchable pydantic_ai.Agent whose run() returns `output`."""
    agent_instance = MagicMock()
    agent_instance.run = AsyncMock(return_value=MagicMock(output=output))
    agent_cls = MagicMock(return_value=agent_instance)
    return agent_cls


def _patched_agent(agent_cls):
    """Patch in *agent_cls* as pydantic_ai.Agent with a stub model resolver."""
    return (
        patch("zrb.llm.capabilities.hook.execution.creator.resolve_configured_model"),
        patch.dict("sys.modules", {"pydantic_ai": MagicMock(Agent=agent_cls)}),
    )


@pytest.mark.asyncio
async def test_agent_hook_no_model_configured():
    config = AgentHookConfig(system_prompt="sp", model=None)
    hook = create_agent_hook(config)
    context = HookContext(event=HookEvent.NOTIFICATION, event_data={})

    with patch("zrb.llm.capabilities.hook.execution.creator.CFG") as mock_cfg:
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
    with mock_config as mock_resolve_model, mock_module:
        mock_resolve_model.return_value = "resolved"
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
    with mock_config as mock_resolve_model, mock_module:
        mock_resolve_model.return_value = "resolved"
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
    with mock_config as mock_resolve_model, mock_module:
        mock_resolve_model.return_value = "resolved"
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
    with mock_config as mock_resolve_model, mock_module:
        mock_resolve_model.return_value = "resolved"
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
    with mock_config as mock_resolve_model, mock_module:
        mock_resolve_model.return_value = "resolved"
        result = await hook(context)

    assert result.success is True
    assert result.modifications == {}


@pytest.mark.asyncio
async def test_agent_hook_skips_llm_call_when_no_named_tools_resolve():
    """When every tool the config names fails to resolve (e.g. the memory
    tools while LLM_MEMORY_ENABLED is off), the hook must not spend an LLM
    call it cannot do anything useful with."""
    config = AgentHookConfig(system_prompt="sp", model="fake-model", tools=["Remember"])
    hook = create_agent_hook(config)
    context = HookContext(event=HookEvent.STOP, event_data={"wrote_files": True})

    agent_cls = _agent_returning("should never run")
    mock_config, mock_module = _patched_agent(agent_cls)
    with (
        patch(
            "zrb.llm.contracts.shared.tool_registry.tool_registry.get_tools",
            return_value=[],
        ),
        patch(
            "zrb.llm.contracts.shared.tool_registry.tool_registry.get_tool_factories",
            return_value=[],
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
    """A resolved tool's `[SYSTEM SUGGESTION]` ValueError (a path check is one
    real example) must come back as a tool result the judge
    model can react to, not an exception that aborts the whole hook run —
    the same containment `create_agent()` gives every other agent's tools."""
    from zrb.llm.engine.agent.hook_agent import resolve_agent_hook_tools

    def flaky_tool() -> str:
        raise ValueError("[SYSTEM SUGGESTION]: link target does not exist.")

    flaky_tool.__name__ = "FlakyTool"

    with (
        patch(
            "zrb.llm.contracts.shared.tool_registry.tool_registry.get_tools",
            return_value=[flaky_tool],
        ),
        patch(
            "zrb.llm.contracts.shared.tool_registry.tool_registry.get_tool_factories",
            return_value=[],
        ),
    ):
        resolved = resolve_agent_hook_tools(["FlakyTool"])

    assert len(resolved) == 1
    result = await resolved[0].function()
    assert result.metadata.get("error") is True
    assert "does not exist" in result.return_value


@pytest.mark.asyncio
async def test_resolved_agent_hook_tools_are_undeferred():
    """A tool registered with `defer_loading=True` for the main agent's rare
    use must reach the hook agent
    with `defer_loading=False` — the hook names it explicitly, so deferring it
    here would only force a wasted search-then-call round trip on every run."""
    from pydantic_ai import Tool

    from zrb.llm.engine.agent.hook_agent import resolve_agent_hook_tools

    def deferred_tool() -> str:
        return "ok"

    deferred_tool.__name__ = "DeferredTool"

    with (
        patch(
            "zrb.llm.contracts.shared.tool_registry.tool_registry.get_tools",
            return_value=[],
        ),
        patch(
            "zrb.llm.contracts.shared.tool_registry.tool_registry.get_tool_factories",
            return_value=[lambda ctx: [Tool(deferred_tool, defer_loading=True)]],
        ),
    ):
        resolved = resolve_agent_hook_tools(["DeferredTool"])

    assert len(resolved) == 1
    assert resolved[0].defer_loading is False


@pytest.mark.asyncio
async def test_agent_hook_runs_when_named_tools_do_resolve():
    """The opposite of the skip case: a resolved tool list reaches the agent."""
    config = AgentHookConfig(system_prompt="sp", model="fake-model", tools=["Remember"])
    hook = create_agent_hook(config)
    context = HookContext(event=HookEvent.STOP, event_data={"wrote_files": True})

    def fake_log_activity(note: str) -> str:
        return f"logged: {note}"

    fake_log_activity.__name__ = "Remember"

    agent_cls = _agent_returning("logged")
    with (
        patch(
            "zrb.llm.capabilities.hook.execution.creator.resolve_configured_model"
        ) as mock_resolve_model,
        # Only Agent is swapped (unlike _patched_agent, which replaces the
        # whole pydantic_ai module) — this test inspects the real Tool that
        # wrap_tool builds around the resolved tool, below.
        patch("pydantic_ai.Agent", agent_cls),
        patch(
            "zrb.llm.contracts.shared.tool_registry.tool_registry.get_tools",
            return_value=[fake_log_activity],
        ),
        patch(
            "zrb.llm.contracts.shared.tool_registry.tool_registry.get_tool_factories",
            return_value=[],
        ),
    ):
        mock_resolve_model.return_value = "resolved"
        result = await hook(context)

    assert result.success is True
    # create_agent() wraps tools into a toolset (SafeToolsetWrapper around a
    # FunctionToolset) rather than passing a raw `tools=` kwarg to Agent(...);
    # `.wrapped` is WrapperToolset's own public dataclass field.
    toolsets_passed = agent_cls.call_args.kwargs["toolsets"]
    assert len(toolsets_passed) == 1
    function_toolset = toolsets_passed[0].wrapped
    run_ctx = RunContext(deps=None, model=MagicMock(), usage=MagicMock())
    resolved_tools = await function_toolset.get_tools(run_ctx)
    assert list(resolved_tools) == ["Remember"]
    returned = await function_toolset.call_tool(
        "Remember", {"note": "x"}, run_ctx, resolved_tools["Remember"]
    )
    assert returned.return_value == "logged: x"


@pytest.mark.asyncio
async def test_an_auto_approving_config_reaches_the_agent():
    """A hook has no UI to answer a deferred call, so the flag must reach the agent."""
    config = AgentHookConfig(
        system_prompt="sp", model="fake-model", tools=["Remember"], auto_approve=True
    )
    hook = create_agent_hook(config)
    context = HookContext(event=HookEvent.STOP, event_data={"wrote_files": True})
    agent = MagicMock()
    agent.run = AsyncMock(
        return_value=SimpleNamespace(output="ok", new_messages=lambda: [])
    )

    def fake_remember(note: str) -> str:
        return note

    fake_remember.__name__ = "Remember"

    with (
        patch(
            "zrb.llm.capabilities.hook.execution.creator.resolve_configured_model",
            return_value="resolved",
        ),
        patch(
            "zrb.llm.capabilities.hook.execution.creator.create_agent",
            return_value=agent,
        ) as create,
        patch(
            "zrb.llm.engine.agent.hook_agent.resolve_agent_hook_tools",
            return_value=[fake_remember],
        ),
    ):
        result = await hook(context)

    assert result.success is True
    assert create.call_args.kwargs["yolo"] is True


@pytest.mark.asyncio
async def test_a_config_note_follows_the_event_in_the_turn():
    """A hook can need the state of a file and not only the event.

    The memory reviewer is handed the day's body that way: a config is built once
    and outlives many turns, so its note is a function of the context rather than
    a string fixed at registration.
    """
    config = AgentHookConfig(
        system_prompt="sp",
        model="fake-model",
        input_note=lambda context: "the page is full",
    )
    hook = create_agent_hook(config)
    context = HookContext(event=HookEvent.STOP, event_data={"a": 1})

    agent_cls = _agent_returning("plain")
    mock_config, mock_module = _patched_agent(agent_cls)
    with mock_config as mock_resolve_model, mock_module:
        mock_resolve_model.return_value = "resolved"
        await hook(context)

    assert agent_cls.return_value.run.call_args.args[0] == (
        "{'a': 1}\n\nthe page is full"
    )


@pytest.mark.asyncio
async def test_a_note_that_cannot_be_built_leaves_the_turn_as_it_was():
    """A note is read off the store, which can be unreadable.

    The reviewer is fire-and-forget: a turn it never saw is a turn nobody
    recorded, so a missing paragraph is the cheaper failure.
    """

    def unreadable(context):
        raise OSError("the store cannot be read")

    config = AgentHookConfig(
        system_prompt="sp", model="fake-model", input_note=unreadable
    )
    hook = create_agent_hook(config)
    context = HookContext(event=HookEvent.STOP, event_data={"a": 1})

    agent_cls = _agent_returning("plain")
    mock_config, mock_module = _patched_agent(agent_cls)
    with mock_config as mock_resolve_model, mock_module:
        mock_resolve_model.return_value = "resolved"
        result = await hook(context)

    assert result.success is True
    assert agent_cls.return_value.run.call_args.args[0] == "{'a': 1}"


@pytest.mark.asyncio
async def test_agent_hook_exception_returns_failure():
    config = AgentHookConfig(system_prompt="sp", model="fake-model")
    hook = create_agent_hook(config)
    context = HookContext(event=HookEvent.NOTIFICATION, event_data={"a": 1})

    mock_config, mock_module = _patched_agent(
        MagicMock(side_effect=RuntimeError("boom"))
    )
    with mock_config as mock_resolve_model, mock_module:
        mock_resolve_model.return_value = "resolved"
        result = await hook(context)

    assert result.success is False
    assert "boom" in (result.output or "")


_SRC = Path(__file__).resolve().parents[4] / "src"

# Imports the hook and nothing else — never `zrb.llm.orchestration.common_tools` — so the
# built-in tools have to come from the engine.
_NO_HOST_PROBE = """
import sys
from zrb.llm.engine.agent.hook_agent import resolve_agent_hook_tools

print(len(resolve_agent_hook_tools(["Read"])), "zrb.llm.orchestration.common_tools" in sys.modules)
"""


def test_a_hook_resolves_a_built_in_tool_with_no_host_imported():
    """A hook fires outside any task run, so its lookup cannot go through a host.

    The sub-agent manager was the only thing that answered "what is `Read`?",
    and the registry behind it was seeded by `zrb.llm.orchestration.common_tools` — an
    orchestration module a hook could reach only by importing the layer above
    it. A fresh interpreter that never imports it is the proof that the built-in
    set is the engine's: the hook reads `tool_registry`, which
    `agent/tool_seed.py` fills as the hook imports it.
    """
    result = subprocess.run(
        [sys.executable, "-c", _NO_HOST_PROBE],
        capture_output=True,
        text=True,
        cwd=_SRC.parent,
        env={**os.environ, "PYTHONPATH": str(_SRC)},
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.split() == ["1", "False"], result.stdout


def test_a_hook_resolves_a_tool_a_host_registered_on_the_manager():
    """A host's own registration is part of what delegation offers.

    `SubAgentManager.append_tool` is public, and a hook naming such a tool in
    its `tools:` list resolved it before this module stopped importing the
    manager. It still does: the manager is read through
    `shared/delegation_api.py`, which the subagent package registers into, so
    the agent package never imports the layer above it.
    """
    from zrb.llm.orchestration.subagent.manager.manager import sub_agent_manager

    def HostTool(ctx):
        return "host"

    sub_agent_manager.append_tool(HostTool)
    try:
        resolved = resolve_agent_hook_tools(["HostTool"])
    finally:
        sub_agent_manager.tool_registry_overrides.pop("HostTool", None)

    assert [resolved_tool_name(tool) for tool in resolved] == ["HostTool"]


def test_a_host_tool_beats_a_shipped_tool_of_the_same_name():
    """A name collision resolves the way it does for a sub-agent: the host's.

    The manager's registry is the shared one with the host's entries laid over
    it, so a hook asking for a name both provide gets the host's copy.
    """
    shipped = tool_registry.tools_by_name()["Read"]

    def Read(ctx):
        return "host's read"

    from zrb.llm.orchestration.subagent.manager.manager import sub_agent_manager

    sub_agent_manager.append_tool(Read)
    try:
        resolved = resolve_agent_hook_tools(["Read"])
    finally:
        sub_agent_manager.tool_registry_overrides.pop("Read", None)

    assert len(resolved) == 1
    assert resolved[0] is not shipped
