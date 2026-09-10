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


def _stub_task(name: str) -> MagicMock:
    task = MagicMock(spec=AnyTask)
    task.name = name
    task.readiness_checks = []
    task.successors = []
    task.fallbacks = []
    task.upstreams = []
    task.color = None
    task.icon = None
    return task


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


def test_register_task_detects_circular_dependency(session):
    """Mutually-upstream tasks must fail fast, not recurse forever."""
    a = _mk_task("a")
    b = _mk_task("b")
    a.upstreams = [b]
    b.upstreams = [a]

    with pytest.raises(ValueError, match="Circular task dependency"):
        session.register_task(a)


def test_register_task_diamond_links_shared_upstream_once(session):
    """A diamond (shared upstream reached via two branches) registers cleanly."""
    root = _mk_task("root")
    left = _mk_task("left")
    right = _mk_task("right")
    sink = _mk_task("sink")
    left.upstreams = [root]
    right.upstreams = [root]
    sink.upstreams = [left, right]

    session.register_task(sink)

    for name in ("root", "left", "right", "sink"):
        assert name in session.task_names
    # The shared upstream's downstreams contain both branches exactly once.
    assert session.get_next_tasks(root) == [left, right]
    # sink's root is the shared upstream.
    assert session.get_root_tasks(sink) == [root]


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


@pytest.mark.asyncio
async def test_failing_deferred_action_does_not_wait_for_a_never_ending_sibling(
    session,
):
    """A crashed long-running task must fail the run immediately.

    Regression: deferred action bodies were gathered with settle-all semantics,
    but a long-running task's body never returns on its own. Running `frontend`
    + `backend` where one crashes then blocked until the survivor was killed
    instead of exiting non-zero. The survivor must be cancelled.
    """
    cancelled = asyncio.Event()

    async def serves_forever():
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            cancelled.set()
            raise

    async def crashes():
        await asyncio.sleep(0.01)
        raise RuntimeError("backend died")

    session.defer_action(_stub_task("frontend"), serves_forever())
    session.defer_action(_stub_task("backend"), crashes())

    with pytest.raises(RuntimeError, match="backend died"):
        await asyncio.wait_for(session.wait_deferred(), timeout=5)

    assert cancelled.is_set()


@pytest.mark.asyncio
async def test_failing_monitoring_coro_cancels_the_polling_siblings(session):
    """Monitoring loops poll forever by design, so the same rule applies."""
    cancelled = asyncio.Event()

    async def polls_forever():
        try:
            while True:
                await asyncio.sleep(0.01)
        except asyncio.CancelledError:
            cancelled.set()
            raise

    async def crashes():
        raise RuntimeError("trigger died")

    session.defer_monitoring(_stub_task("poller"), polls_forever())
    session.defer_monitoring(_stub_task("trigger"), crashes())

    with pytest.raises(RuntimeError, match="trigger died"):
        await asyncio.wait_for(session.wait_deferred(), timeout=5)

    assert cancelled.is_set()


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


@pytest.mark.asyncio
async def test_defer_coro_after_terminate_is_cancelled():
    """Coros deferred after terminate() are cancelled, not run (regression)."""
    from zrb.context.shared_context import SharedContext

    shared_ctx = SharedContext()
    session = Session(shared_ctx=shared_ctx)
    session.terminate()

    ran = False

    async def sample():
        nonlocal ran
        ran = True

    session.defer_coro(sample())
    await session.wait_deferred()
    # Yield to let any (incorrectly) scheduled task run before asserting.
    await asyncio.sleep(0)
    assert ran is False


@pytest.mark.asyncio
async def test_defer_action_after_terminate_is_cancelled():
    """Actions deferred after terminate() are cancelled, not run (regression)."""
    from zrb.context.shared_context import SharedContext

    shared_ctx = SharedContext()
    session = Session(shared_ctx=shared_ctx)
    session.terminate()

    task = MagicMock(spec=AnyTask)
    task.name = "task"
    task.readiness_checks = []
    task.successors = []
    task.fallbacks = []
    task.upstreams = []
    task.color = None
    task.icon = None

    ran = False

    async def sample():
        nonlocal ran
        ran = True

    session.defer_action(task, sample())
    await session.wait_deferred()
    await asyncio.sleep(0)
    assert ran is False


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
    task.inputs = []

    session.register_task(task)
    state_log = session.as_state_log()

    assert state_log.name == session.name
    assert "task" in state_log.task_status


def test_as_state_log_masks_secret_input():
    """Secret input values must be masked before reaching the state log."""
    from zrb.context.shared_context import SharedContext
    from zrb.input.password_input import PasswordInput
    from zrb.session.session import SECRET_MASK

    shared_ctx = SharedContext()
    shared_ctx.input["password"] = "hunter2"
    shared_ctx.input["plain"] = "visible"

    password_input = PasswordInput(name="password")
    other_input = MagicMock()
    other_input.name = "plain"
    other_input.is_secret = False
    task = MagicMock(spec=AnyTask)
    task.name = "mytask"
    task.readiness_checks = []
    task.successors = []
    task.fallbacks = []
    task.upstreams = []
    task.color = None
    task.icon = None
    task.inputs = [password_input, other_input]

    session = Session(shared_ctx=shared_ctx)
    session.register_task(task)
    state_log = session.as_state_log()

    assert state_log.input["password"] == SECRET_MASK
    assert "hunter2" not in str(state_log.input)
    assert state_log.input["plain"] == "visible"


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
