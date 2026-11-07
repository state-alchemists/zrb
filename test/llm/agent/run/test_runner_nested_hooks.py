"""A nested run's events must be tellable from the user's own turn.

A listener that paints a state from these events — the face, which repaints
"thinking" on a prompt and "tool" on a tool call — otherwise shows the user's
turn as still running after it has ended, because a run started inside a hook
announces itself exactly like a prompt does and nothing that follows says
"idle" for it.
"""

from unittest.mock import MagicMock

import pytest
from pydantic_ai import AgentRunResultEvent

from zrb.llm.agent.run.runner import run_agent
from zrb.llm.shared.agent_state import is_current_run_nested
from zrb.llm.config.limiter import LLMLimiter
from zrb.llm.hook.contracts.interface import HookResult
from zrb.llm.hook.manager import HookManager
from zrb.llm.hook.contracts.types import HookEvent

from .test_runner_lifecycle import _run_from


async def _run_marked(nested: bool) -> tuple[bool, dict]:
    """Run one turn, marked (or not) as nested; return what a hook and a tool see."""
    payloads: list[dict] = []

    async def capture(context):
        payloads.append(dict(context.event_data))
        return HookResult()

    manager = HookManager(search_dirs=[])
    manager.add_hook(capture, events=[HookEvent.USER_PROMPT_SUBMIT])

    seen_by_tools: list[bool] = []

    async def _gen(*args, **kwargs):
        seen_by_tools.append(is_current_run_nested())
        result = MagicMock()
        result.output = "done"
        result.all_messages.return_value = []
        yield AgentRunResultEvent(result=result)

    agent = MagicMock()
    agent.run = _run_from(_gen)
    await run_agent(
        agent=agent,
        message="hi",
        message_history=[],
        limiter=LLMLimiter(),
        hook_manager=manager,
        nested=nested,
    )
    return seen_by_tools[0], payloads[0]


@pytest.mark.asyncio
async def test_the_users_own_turn_is_not_marked_nested():
    seen_by_tools, payload = await _run_marked(False)

    assert seen_by_tools is False
    assert payload["nested_run"] is False


@pytest.mark.asyncio
async def test_a_run_started_from_a_hook_is_marked_nested():
    """The memory reviewer's run, a sub-agent's, a skill's: a listener must be
    able to skip them without skipping the user's turn."""
    seen_by_tools, payload = await _run_marked(True)

    assert seen_by_tools is True
    assert payload["nested_run"] is True
