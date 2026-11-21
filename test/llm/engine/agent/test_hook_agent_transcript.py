"""What a hook is handed: the turn, capped, without the writer's thinking.

The scaffold is `test_hook_agent.py`'s — the same patched `pydantic_ai.Agent`
and model resolver — because this is the same callable, read for what reaches
it rather than for what it returns.
"""

import pytest
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    ThinkingPart,
    ToolCallPart,
    ToolReturnPart,
)
from test_hook_agent import _agent_returning, _patched_agent

from zrb.llm.capabilities.hook.contracts.interface import HookContext
from zrb.llm.capabilities.hook.contracts.schema import AgentHookConfig
from zrb.llm.capabilities.hook.contracts.types import HookEvent
from zrb.llm.engine.agent.hook_agent import create_agent_hook


@pytest.mark.asyncio
async def test_a_hook_reads_a_capped_transcript_without_the_writers_thinking():
    """The reviewer is handed the turn, with one cap on it (#989).

    A hook fires outside the turn loop, so its opening request reads no cached
    prefix and pays nearly all of its prompt fresh; the measured turns were
    24–58% tool returns and 1–11% tool calls, which is where the cap goes. Both
    ends of a return survive with the gap named — a head-only cut can invert
    what the return said — and a memory tool's return arrives whole, because
    that is what a claim is read out of.
    """
    shell_output = "HEAD-MARK" + "x" * 5_000 + "TAIL-MARK"
    memory_output = "MEMORY-HEAD" + "y" * 5_000 + "MEMORY-TAIL"
    turn = [
        ModelResponse(
            parts=[
                ThinkingPart(content="the writer's own deliberation"),
                ToolCallPart(tool_name="Shell", args={"cmd": "ls"}, tool_call_id="c1"),
                ToolCallPart(
                    tool_name="Remember", args={"note": "x"}, tool_call_id="c2"
                ),
                TextPart(content="done"),
            ]
        ),
        ModelRequest(
            parts=[
                ToolReturnPart(
                    tool_name="Shell", content=shell_output, tool_call_id="c1"
                ),
                ToolReturnPart(
                    tool_name="Remember", content=memory_output, tool_call_id="c2"
                ),
            ]
        ),
    ]
    config = AgentHookConfig(system_prompt="sp", model="fake-model")
    hook = create_agent_hook(config)
    context = HookContext(event=HookEvent.STOP, event_data={"turn": turn})

    agent_cls = _agent_returning("plain")
    mock_config, mock_module = _patched_agent(agent_cls)
    with mock_config as mock_resolve_model, mock_module:
        mock_resolve_model.return_value = "resolved"
        await hook(context)

    user_input = agent_cls.return_value.run.call_args.args[0]
    assert "HEAD-MARK" in user_input
    assert "TAIL-MARK" in user_input
    assert "TRUNCATED" in user_input
    assert memory_output in user_input
    assert "deliberation" not in user_input
