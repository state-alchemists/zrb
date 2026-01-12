import asyncio
from unittest.mock import MagicMock, Mock

import pytest

from zrb.context.any_shared_context import AnySharedContext
from zrb.session.session import Session
from zrb.task.any_task import AnyTask
from zrb.task_status.task_status import TaskStatus
from zrb.xcom.xcom import Xcom


@pytest.fixture
def mock_shared_ctx():
    shared_ctx = Mock(spec=AnySharedContext)
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
    task = Mock(spec=AnyTask)
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
    upstream = Mock(spec=AnyTask)
    upstream.name = "upstream"
    upstream.readiness_checks = []
    upstream.successors = []
    upstream.fallbacks = []
    upstream.upstreams = []
    upstream.color = None
    upstream.icon = None

    task = Mock(spec=AnyTask)
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
    task = Mock(spec=AnyTask)
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
    upstream = Mock(spec=AnyTask)
    upstream.name = "upstream"
    upstream.readiness_checks = []
    upstream.successors = []
    upstream.fallbacks = []
    upstream.upstreams = []
    upstream.color = None
    upstream.icon = None

    task = Mock(spec=AnyTask)
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
    task = Mock(spec=AnyTask)
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
    task = Mock(spec=AnyTask)
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
    task = Mock(spec=AnyTask)
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
    task = Mock(spec=AnyTask)
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
    task = Mock(spec=AnyTask)
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
