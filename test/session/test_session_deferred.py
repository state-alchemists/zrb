import asyncio
from unittest.mock import MagicMock

import pytest

from zrb.context.any_shared_context import AnySharedContext
from zrb.session.session import Session
from zrb.task.any_task import AnyTask


@pytest.fixture
def mock_shared_ctx():
    shared_ctx = MagicMock(spec=AnySharedContext)
    shared_ctx.xcom = {}
    shared_ctx.input = {}
    shared_ctx.shared_log = []
    return shared_ctx


@pytest.fixture
def session(mock_shared_ctx):
    return Session(shared_ctx=mock_shared_ctx)


def _mk_task(name):
    t = MagicMock(spec=AnyTask)
    t.name = name
    t.readiness_checks = []
    t.successors = []
    t.fallbacks = []
    t.upstreams = []
    t.color = None
    t.icon = None
    return t


@pytest.mark.asyncio
async def test_defer_action_with_asyncio_task():
    """Test defer_action with an already-created asyncio.Task."""
    from zrb.context.shared_context import SharedContext

    shared_ctx = SharedContext()
    session = Session(shared_ctx=shared_ctx)

    task = MagicMock(spec=AnyTask)
    task.name = "task"
    task.readiness_checks = []
    task.successors = []
    task.fallbacks = []
    task.upstreams = []
    task.color = None
    task.icon = None

    async def sample():
        return "done"

    asyncio_task = asyncio.create_task(sample())
    session.defer_action(task, asyncio_task)  # Pass an asyncio.Task, not a coro

    await session.wait_deferred()


@pytest.mark.asyncio
async def test_defer_coro_with_asyncio_task():
    """Test defer_coro with an asyncio.Task."""
    from zrb.context.shared_context import SharedContext

    shared_ctx = SharedContext()
    session = Session(shared_ctx=shared_ctx)

    async def sample():
        return "done"

    asyncio_task = asyncio.create_task(sample())
    session.defer_coro(asyncio_task)  # Pass asyncio.Task

    await session.wait_deferred()


def test_register_task_with_readiness_checks():
    """Test register_task with readiness checks."""
    from zrb.context.shared_context import SharedContext

    shared_ctx = SharedContext()
    session = Session(shared_ctx=shared_ctx)

    check_task = MagicMock(spec=AnyTask)
    check_task.name = "check"
    check_task.readiness_checks = []
    check_task.successors = []
    check_task.fallbacks = []
    check_task.upstreams = []
    check_task.color = None
    check_task.icon = None

    main_task = MagicMock(spec=AnyTask)
    main_task.name = "main"
    main_task.readiness_checks = [check_task]
    main_task.successors = []
    main_task.fallbacks = []
    main_task.upstreams = []
    main_task.color = None
    main_task.icon = None

    session.register_task(main_task)

    # Both main and check should be registered
    assert "main" in session.task_names
    assert "check" in session.task_names


def test_get_root_tasks_with_visited_cycle():
    """Test get_root_tasks handles already-visited tasks."""
    from zrb.context.shared_context import SharedContext

    shared_ctx = SharedContext()
    session = Session(shared_ctx=shared_ctx)

    upstream = MagicMock(spec=AnyTask)
    upstream.name = "upstream"
    upstream.readiness_checks = []
    upstream.successors = []
    upstream.fallbacks = []
    upstream.upstreams = []
    upstream.color = None
    upstream.icon = None

    task1 = MagicMock(spec=AnyTask)
    task1.name = "task1"
    task1.readiness_checks = []
    task1.successors = []
    task1.fallbacks = []
    task1.upstreams = [upstream]
    task1.color = None
    task1.icon = None

    task2 = MagicMock(spec=AnyTask)
    task2.name = "task2"
    task2.readiness_checks = []
    task2.successors = []
    task2.fallbacks = []
    task2.upstreams = [upstream]
    task2.color = None
    task2.icon = None

    session.register_task(task1)
    session.register_task(task2)

    # Both tasks share the same upstream - upstream should appear only once in roots
    roots1 = session.get_root_tasks(task1)
    roots2 = session.get_root_tasks(task2)

    assert upstream in roots1
    assert upstream in roots2
    # No duplicates
    assert roots1.count(upstream) == 1


@pytest.mark.asyncio
async def test_wait_deferred_drains_coros_deferred_during_wait():
    """A coro deferred WHILE wait_deferred is running is still awaited.

    Trigger callbacks defer new coros mid-wait; a single gather over a
    snapshot would return before they finish.
    """
    shared_ctx = MagicMock(spec=AnySharedContext)
    session = Session(shared_ctx=shared_ctx)
    done = []

    async def second():
        done.append("second")

    async def first():
        await asyncio.sleep(0.01)
        session.defer_coro(second())
        done.append("first")

    session.defer_coro(first())
    await session.wait_deferred()
    assert done == ["first", "second"]


@pytest.mark.asyncio
async def test_defer_coro_prune_logs_failed_coro():
    """Pruning a finished-and-failed coro retrieves and logs its exception."""
    from unittest.mock import patch

    shared_ctx = MagicMock(spec=AnySharedContext)
    session = Session(shared_ctx=shared_ctx)

    async def boom():
        raise ValueError("deferred failure")

    async def ok():
        pass

    with patch("zrb.session.session.CFG") as mock_cfg:
        session.defer_coro(boom())
        await asyncio.sleep(0.01)  # let it fail
        session.defer_coro(ok())  # triggers pruning of the failed coro
        mock_cfg.LOGGER.error.assert_called_once()
        assert "deferred failure" in mock_cfg.LOGGER.error.call_args.args[0]
    await session.wait_deferred()


@pytest.mark.asyncio
async def test_defer_action_cancels_previous_orphan():
    """Re-deferring a task must cancel the previous still-running action
    instead of leaving it orphaned (never awaited, invisible to terminate)."""
    from zrb.context.shared_context import SharedContext

    shared_ctx = SharedContext()
    session = Session(shared_ctx=shared_ctx)
    task = _mk_task("redeferred")

    started_first = asyncio.Event()
    cancelled_first = asyncio.Event()

    async def first_action():
        started_first.set()
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            cancelled_first.set()
            raise

    async def second_action():
        return "second"

    session.defer_action(task, first_action())
    await asyncio.wait_for(started_first.wait(), timeout=1)

    session.defer_action(task, second_action())

    # Give the cancellation a moment to land.
    for _ in range(50):
        if cancelled_first.is_set():
            break
        await asyncio.sleep(0.01)
    assert cancelled_first.is_set()
