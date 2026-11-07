"""Every hook payload says which run it belongs to.

The state a listener paints — the avatar's face is one — belongs to the user's
turn, not to a run a hook started. The flag is stamped once, in
`execute_hooks`, so an event added later cannot go out without it.
"""

import pytest

from zrb.llm.shared.agent_state import current_nested_run
from zrb.llm.hook.contracts.interface import HookResult
from zrb.llm.hook.manager import HookManager
from zrb.llm.hook.contracts.types import HookEvent

_EVENTS = [
    HookEvent.USER_PROMPT_SUBMIT,
    HookEvent.PRE_TOOL_USE,
    HookEvent.POST_TOOL_USE,
    HookEvent.PERMISSION_REQUEST,
    HookEvent.PERMISSION_RESOLVED,
    HookEvent.STOP_FAILURE,
    HookEvent.PRE_COMPACT,
    HookEvent.SESSION_END,
]


async def _payloads(nested: bool) -> list[dict]:
    seen: list[dict] = []

    async def capture(context):
        seen.append(dict(context.event_data))
        return HookResult()

    manager = HookManager(search_dirs=[])
    manager.add_hook(capture, events=_EVENTS)
    token = current_nested_run.set(nested)
    try:
        for event in _EVENTS:
            await manager.execute_hooks(event, {"something": 1})
    finally:
        current_nested_run.reset(token)
    return seen


@pytest.mark.asyncio
async def test_a_nested_run_says_so_on_every_event():
    payloads = await _payloads(True)

    assert len(payloads) == len(_EVENTS)
    assert all(payload["nested_run"] is True for payload in payloads)


@pytest.mark.asyncio
async def test_the_users_turn_says_so_on_every_event():
    payloads = await _payloads(False)

    assert len(payloads) == len(_EVENTS)
    assert all(payload["nested_run"] is False for payload in payloads)
