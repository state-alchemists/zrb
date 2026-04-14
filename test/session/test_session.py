import asyncio
from unittest.mock import MagicMock

import pytest

from zrb.context.any_shared_context import AnySharedContext
from zrb.session.session import Session
from zrb.task.any_task import AnyTask
from zrb.task_status.task_status import TaskStatus
from zrb.xcom.xcom import Xcom


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


def test_session_init(session, mock_shared_ctx):
    assert session.name is not None
    assert session.shared_ctx == mock_shared_ctx
    assert not session.is_terminated
    assert session.parent is None
    assert session.root_group is None


def test_register_task(session):
    task = MagicMock(spec=AnyTask)
    task.name = "task1"
    task.readiness_checks = []
    task.successors = []
    task.fallbacks = []
    task.upstreams = []
    task.color = None
    task.icon = None

    session.register_task(task)

    assert task.name in session.task_names
    assert isinstance(session.get_task_status(task), TaskStatus)
    # Check XCom initialization
    assert task.name in session.shared_ctx.xcom
    assert isinstance(session.shared_ctx.xcom[task.name], Xcom)


def test_register_task_with_dependencies(session):
    upstream = MagicMock(spec=AnyTask)
    upstream.name = "upstream"
    upstream.readiness_checks = []
    upstream.successors = []
    upstream.fallbacks = []
    upstream.upstreams = []
    upstream.color = None
    upstream.icon = None

    task = MagicMock(spec=AnyTask)
    task.name = "task"
    task.readiness_checks = []
    task.successors = []
    task.fallbacks = []
    task.upstreams = [upstream]
    task.color = None
    task.icon = None

    session.register_task(task)

    assert "task" in session.task_names
    assert "upstream" in session.task_names

    # Check if relationships are correctly built
    # We can indirectly verify by checking is_allowed_to_run or get_root_tasks
    roots = session.get_root_tasks(task)
    assert upstream in roots
    assert (
        task not in roots
    )  # task has upstream, so it's not a root relative to itself in isolation?
    # Wait, get_root_tasks logic: if no upstreams, append self. else recursive.
    # So roots of 'task' should be ['upstream'].


def test_is_allowed_to_run(session):
    task = MagicMock(spec=AnyTask)
    task.name = "task"
    task.readiness_checks = []
    task.successors = []
    task.fallbacks = []
    task.upstreams = []
    task.color = None
    task.icon = None

    session.register_task(task)

    # No upstreams, not started -> allowed
    assert session.is_allowed_to_run(task)

    # Mark started
    session.get_task_status(task).mark_as_started()
    assert not session.is_allowed_to_run(task)


def test_is_allowed_to_run_with_upstream(session):
    upstream = MagicMock(spec=AnyTask)
    upstream.name = "upstream"
    upstream.readiness_checks = []
    upstream.successors = []
    upstream.fallbacks = []
    upstream.upstreams = []
    upstream.color = None
    upstream.icon = None

    task = MagicMock(spec=AnyTask)
    task.name = "task"
    task.readiness_checks = []
    task.successors = []
    task.fallbacks = []
    task.upstreams = [upstream]
    task.color = None
    task.icon = None

    session.register_task(task)

    # Upstream not ready -> not allowed
    assert not session.is_allowed_to_run(task)

    # Complete upstream
    session.get_task_status(upstream).mark_as_completed()
    session.get_task_status(upstream).mark_as_ready()
    assert session.is_allowed_to_run(task)


def test_terminate(session):
    session.terminate()
    assert session.is_terminated


@pytest.mark.asyncio
async def test_defer_action_and_wait(session):
    task = MagicMock(spec=AnyTask)
    task.name = "task"
    task.readiness_checks = []
    task.successors = []
    task.fallbacks = []
    task.upstreams = []
    task.color = None
    task.icon = None

    async def sample_coro():
        return "done"

    session.defer_action(task, sample_coro())

    # Verify task is registered
    assert task.name in session.task_names

    await session.wait_deferred()
    # If no error, pass. We can't easily check internal state of done coros from public API
    # without accessing private members, but wait_deferred should essentially wait for them.


@pytest.mark.asyncio
async def test_defer_monitoring_and_wait(session):
    task = MagicMock(spec=AnyTask)
    task.name = "task"
    task.readiness_checks = []
    task.successors = []
    task.fallbacks = []
    task.upstreams = []
    task.color = None
    task.icon = None

    session.defer_monitoring(task, asyncio.sleep(0.01))
    await session.wait_deferred()


@pytest.mark.asyncio
async def test_defer_coro_and_wait(session):
    session.defer_coro(asyncio.sleep(0.01))
    await session.wait_deferred()


def test_context_creation(session):
    task = MagicMock(spec=AnyTask)
    task.name = "task"
    task.readiness_checks = []
    task.successors = []
    task.fallbacks = []
    task.upstreams = []
    task.color = None
    task.icon = None

    ctx = session.get_ctx(task)
    # assert ctx.task_name == "task" # Not exposed
    assert ctx.input == session.shared_ctx.input


def test_final_result(session):
    task = MagicMock(spec=AnyTask)
    task.name = "main_task"
    task.readiness_checks = []
    task.successors = []
    task.fallbacks = []
    task.upstreams = []
    task.color = None
    task.icon = None

    session.set_main_task(task)

    # Push result to XCom
    session.shared_ctx.xcom[task.name].push("result")

    assert session.final_result == "result"


def test_final_result_no_main_task(session):
    assert session.final_result is None


def test_as_state_log(session):
    task = MagicMock(spec=AnyTask)
    task.name = "task"
    task.readiness_checks = []
    task.successors = []
    task.fallbacks = []
    task.upstreams = []
    task.color = None
    task.icon = None

    session.register_task(task)
    state_log = session.as_state_log()

    assert state_log.name == session.name
    assert "task" in state_log.task_status


def test_as_state_log_with_non_serializable_input():
    """Test as_state_log handles non-JSON-serializable inputs."""
    from zrb.context.shared_context import SharedContext

    shared_ctx = SharedContext()
    session = Session(shared_ctx=shared_ctx)

    # Add a non-serializable value to input
    shared_ctx.input["normal"] = "value"

    # Create a non-serializable object
    class NotSerializable:
        def __repr__(self):
            return "<NotSerializable>"

    shared_ctx.input["bad"] = NotSerializable()

    state_log = session.as_state_log()
    # Should have converted non-serializable to string
    assert "bad" in state_log.input
    assert isinstance(state_log.input["bad"], str)


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
