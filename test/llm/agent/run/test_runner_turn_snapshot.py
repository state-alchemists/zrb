"""The runner's turn-start snapshot for the self-review gate: deleted when the
turn ends however it ends, and never the reason a turn fails."""

import asyncio
import os
import threading
from unittest.mock import MagicMock

import pytest
from pydantic_ai import AgentRunResultEvent

from zrb.llm.agent.run.runner import run_agent
from zrb.llm.config.limiter import LLMLimiter
from zrb.llm.hook.interface import HookContext, HookResult
from zrb.llm.hook.manager import HookManager
from zrb.llm.hook.types import HookEvent
from zrb.util.git.snapshot_store import Snapshot


def _run_from(agen_func):
    """Wrap an async generator function into an ``agent.run(event_stream_handler=...)`` mock.

    ``agen_func`` keeps yielding the same events every test already
    constructs, ending with ``AgentRunResultEvent(result=...)`` (the old
    ``run_stream_events()`` shape). Real pydantic-ai's ``event_stream_handler``
    never receives that trailing event -- it's ``run_stream_events()``'s own
    addition, synthesized by its consumer-facing iterator after the
    background run finishes. This strips it the same way ``_execution_loop``
    does and returns its ``.result`` as ``agent.run()``'s return value.
    """

    async def fake_run(*args, **kwargs):
        handler = kwargs.pop("event_stream_handler", None)
        result_holder = []

        async def events():
            async for event in agen_func(*args, **kwargs):
                if isinstance(event, AgentRunResultEvent):
                    result_holder.append(event.result)
                    return
                yield event

        if handler is not None:
            await handler(MagicMock(), events())
        else:
            async for _ in events():
                pass
        return result_holder[0] if result_holder else None

    return fake_run


@pytest.mark.asyncio
async def test_cancelling_a_turn_mid_snapshot_leaves_no_snapshot_store(monkeypatch):
    """The snapshot runs in a worker thread that cancelling cannot stop, so
    the cancellation waits for it: the store is deleted only once git has
    stopped writing to it, and is gone when the cancellation surfaces."""
    started = threading.Event()
    release = threading.Event()
    finished = threading.Event()
    stores: list[str] = []

    def slow_snapshot(store, deadline=None):
        stores.append(store.git_dir)
        started.set()
        release.wait(5)
        # A git command still running after the turn deleted the store would
        # recreate it.
        os.makedirs(os.path.join(store.git_dir, "objects", "ab"), exist_ok=True)
        finished.set()
        return Snapshot("tree-at-start")

    monkeypatch.setenv("ZRB_LLM_SELF_REVIEW_ENABLED", "on")
    monkeypatch.setattr(
        "zrb.llm.agent.run.turn_snapshot.SnapshotStore.snapshot", slow_snapshot
    )
    monkeypatch.setattr(
        "zrb.llm.hook.manager.register_self_review_hook", lambda manager: None
    )
    turn = asyncio.create_task(
        run_agent(
            agent=MagicMock(),
            message="Hi",
            message_history=[],
            limiter=LLMLimiter(),
            hook_manager=HookManager(search_dirs=[]),
        )
    )
    await asyncio.to_thread(started.wait, 5)

    turn.cancel()
    await asyncio.sleep(0.1)
    waited_for_the_snapshot = not turn.done()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await turn

    assert waited_for_the_snapshot
    assert finished.is_set()
    assert len(stores) == 1
    assert not os.path.exists(stores[0])


@pytest.mark.asyncio
async def test_a_working_directory_that_is_gone_does_not_fail_the_turn(monkeypatch):
    """With self-review on, the turn-start snapshot reads the working
    directory; one deleted mid-session leaves the turn without a snapshot
    instead of failing it."""
    captured: list = []

    async def record(context: HookContext) -> HookResult:
        captured.append(context.event_data)
        return HookResult(success=True)

    class _GoneWorkdir:
        """`os` for the runner alone, with its working directory deleted."""

        def __getattr__(self, name):
            return getattr(os, name)

        def getcwd(self):
            raise FileNotFoundError("the working directory was deleted")

    monkeypatch.setenv("ZRB_LLM_SELF_REVIEW_ENABLED", "on")
    monkeypatch.setattr(
        "zrb.llm.hook.manager.register_self_review_hook", lambda manager: None
    )
    monkeypatch.setattr("zrb.llm.agent.run.runner.os", _GoneWorkdir())
    manager = HookManager(search_dirs=[])
    manager.add_hook(record, events=[HookEvent.STOP])
    agent = MagicMock()
    result = MagicMock()
    result.output = "done"
    result.all_messages.return_value = []

    async def _gen(*args, **kwargs):
        yield AgentRunResultEvent(result=result)

    agent.run = _run_from(_gen)

    output, _ = await run_agent(
        agent=agent,
        message="Hi",
        message_history=[],
        limiter=LLMLimiter(),
        hook_manager=manager,
    )

    assert output == "done"
    assert captured[0]["turn_start_snapshot"] is None
