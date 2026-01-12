import asyncio
from unittest.mock import MagicMock, Mock, patch

import pytest

from zrb.context.any_context import AnyContext
from zrb.context.shared_context import SharedContext
from zrb.session.any_session import AnySession
from zrb.session.session import Session
from zrb.task.any_task import AnyTask
from zrb.task.base_task import BaseTask

# Create a custom mock class to avoid AsyncMock issues
class MockAnySession:
    """Custom mock for AnySession to avoid AsyncMock warnings."""
    def __init__(self):
        self._registered_tasks = []
    
    async def wait_deferred(self):
        return None
    
    def register_task(self, task):
        self._registered_tasks.append(task)
        
    # Add other methods as needed
    def get_task_status(self, task):
        # Return a mock task status
        class MockTaskStatus:
            def __init__(self):
                self.is_completed = False
                self.is_skipped = False
                self.is_failed = False
                
            def mark_as_completed(self):
                self.is_completed = True
                self.is_skipped = False
                self.is_failed = False
                
            def mark_as_skipped(self):
                self.is_completed = False
                self.is_skipped = True
                self.is_failed = False
                
            def mark_as_failed(self):
                self.is_completed = False
                self.is_skipped = False
                self.is_failed = True
        
        return MockTaskStatus()

# Create mock instances
mock_any_session = MockAnySession()
mock_any_context = MagicMock()
mock_any_task = MagicMock()


def test_base_task_init():
    task = BaseTask(name="test_task")
    assert task.name == "test_task"
    assert task.color is None
    assert task.icon is None
    assert task.description == "test_task"
    assert task.cli_only is False


def test_base_task_repr():
    task = BaseTask(name="test_task")
    assert repr(task) == "<BaseTask name=test_task>"


@patch("zrb.task.base_task.handle_rshift")
def test_base_task_rshift(mock_handle_rshift):
    task1 = BaseTask(name="task1")
    task2 = BaseTask(name="task2")
    task1 >> task2
    mock_handle_rshift.assert_called_once_with(task1, task2)


@patch("zrb.task.base_task.handle_lshift")
def test_base_task_lshift(mock_handle_lshift):
    task1 = BaseTask(name="task1")
    task2 = BaseTask(name="task2")
    task1 << task2
    mock_handle_lshift.assert_called_once_with(task1, task2)


def test_base_task_properties():
    task = BaseTask(
        name="test_task",
        color=1,
        icon="icon",
        description="description",
        cli_only=True,
    )
    assert task.name == "test_task"
    assert task.color == 1
    assert task.icon == "icon"
    assert task.description == "description"
    assert task.cli_only is True


@patch("zrb.task.base_task.get_combined_envs")
def test_base_task_envs_property(mock_get_combined_envs):
    task = BaseTask(name="test_task")
    task.envs
    mock_get_combined_envs.assert_called_once_with(task)


@patch("zrb.task.base_task.get_combined_inputs")
def test_base_task_inputs_property(mock_get_combined_inputs):
    task = BaseTask(name="test_task")
    task.inputs
    mock_get_combined_inputs.assert_called_once_with(task)


def test_base_task_fallbacks_property():
    task = BaseTask(name="test_task")
    assert task.fallbacks == []


def test_base_task_append_fallback():
    task = BaseTask(name="test_task")
    task.append_fallback(mock_any_task)
    assert mock_any_task in task.fallbacks


def test_base_task_successors_property():
    task = BaseTask(name="test_task")
    assert task.successors == []


def test_base_task_append_successor():
    task = BaseTask(name="test_task")
    task.append_successor(mock_any_task)
    assert mock_any_task in task.successors


def test_base_task_readiness_checks_property():
    task = BaseTask(name="test_task")
    assert task.readiness_checks == []


def test_base_task_append_readiness_check():
    task = BaseTask(name="test_task")
    task.append_readiness_check(mock_any_task)
    assert mock_any_task in task.readiness_checks


def test_base_task_upstreams_property():
    task = BaseTask(name="test_task")
    assert task.upstreams == []


def test_base_task_append_upstream():
    task = BaseTask(name="test_task")
    task.append_upstream(mock_any_task)
    assert mock_any_task in task.upstreams


@patch("zrb.task.base_task.build_task_context")
def test_base_task_get_ctx(mock_build_task_context):
    task = BaseTask(name="test_task")
    task.get_ctx(mock_any_session)
    mock_build_task_context.assert_called_once_with(task, mock_any_session)


def test_base_task_run():
    async def mock_run_and_cleanup(task, session=None, str_kwargs=None, kwargs=None):
        return None
    
    with patch("zrb.task.base_task.run_and_cleanup", side_effect=mock_run_and_cleanup) as mock_run_and_cleanup:
        with patch("asyncio.run") as mock_asyncio_run:
            task = BaseTask(name="test_task")
            task.run(session=mock_any_session, str_kwargs={"key": "value"})

            mock_run_and_cleanup.assert_called_once_with(
                task, session=mock_any_session, str_kwargs={"key": "value"}, kwargs=None
            )
            # Assert that asyncio.run was called with a coroutine object
            mock_asyncio_run.assert_called_once()
            called_with_arg = mock_asyncio_run.call_args[0][0]
            assert asyncio.iscoroutine(called_with_arg)


@pytest.mark.asyncio
async def test_base_task_async_run():
    # Create a simple async function instead of AsyncMock
    call_args = []

    async def mock_run_task_async(task, session=None, str_kwargs=None, kwargs=None):
        call_args.append((task, session, str_kwargs, kwargs))
        return None

    with patch(
        "zrb.task.base_task.run_task_async",
        new=Mock(side_effect=mock_run_task_async),
    ):
        task = BaseTask(name="test_task")
        await task.async_run(session=mock_any_session, str_kwargs={"key": "value"})
        assert len(call_args) == 1
        assert call_args[0][0] == task
        assert call_args[0][1] == mock_any_session
        assert call_args[0][2] == {"key": "value"}
        assert call_args[0][3] is None


@pytest.mark.asyncio
async def test_base_task_exec_root_tasks():
    # Create a simple async function instead of AsyncMock
    call_args = []

    async def mock_execute_root_tasks(task, session):
        call_args.append((task, session))
        return None

    with patch(
        "zrb.task.base_task.execute_root_tasks",
        new=Mock(side_effect=mock_execute_root_tasks),
    ):
        task = BaseTask(name="test_task")
        await task.exec_root_tasks(mock_any_session)
        assert len(call_args) == 1
        assert call_args[0][0] == task
        assert call_args[0][1] == mock_any_session


@pytest.mark.asyncio
async def test_base_task_exec_chain():
    # Create a simple async function instead of AsyncMock
    call_args = []

    async def mock_execute_task_chain(task, session):
        call_args.append((task, session))
        return None

    with patch(
        "zrb.task.base_task.execute_task_chain",
        new=Mock(side_effect=mock_execute_task_chain),
    ):
        task = BaseTask(name="test_task")
        await task.exec_chain(mock_any_session)
        assert len(call_args) == 1
        assert call_args[0][0] == task
        assert call_args[0][1] == mock_any_session


@pytest.mark.asyncio
async def test_base_task_exec():
    # Create a simple async function instead of AsyncMock
    call_args = []

    async def mock_execute_task_action(task, session):
        call_args.append((task, session))
        return None

    with patch(
        "zrb.task.base_task.execute_task_action",
        new=Mock(side_effect=mock_execute_task_action),
    ):
        task = BaseTask(name="test_task")
        await task.exec(mock_any_session)
        assert len(call_args) == 1
        assert call_args[0][0] == task
        assert call_args[0][1] == mock_any_session



@pytest.mark.asyncio
async def test_base_task_execute_condition_skipped():
    """
    When a task is skipped, its successors should still be executed.
    """
    task1 = BaseTask(name="task1", execute_condition=False)
    task2 = BaseTask(name="task2")
    task3 = BaseTask(name="task3")
    task1 >> task2
    task2 >> task3

    # Create a simple mock class for SharedContext to avoid AsyncMock issues
    class MockSharedContext:
        def __init__(self):
            self.xcom = {}
            self.input = {}
            self._session = None
            self._log = []

        def set_session(self, session):
            self._session = session

        def get_logging_level(self):
            return 20  # logging.INFO

        def append_to_shared_log(self, message):
            self._log.append(message)

        @property
        def session(self):
            return self._session

        @session.setter
        def session(self, value):
            self._session = value

        # Add other required properties
        @property
        def env(self):
            return {}

        @property
        def args(self):
            return []

        @property
        def shared_log(self):
            return self._log

        def render(self, template):
            return template

        @property
        def is_web_mode(self):
            return False

        @property
        def is_tty(self):
            return True

    shared_ctx = MockSharedContext()
    session = Session(shared_ctx=shared_ctx)
    shared_ctx.session = session
    session.register_task(task1)
    session.register_task(task2)
    session.register_task(task3)

    call_count = 0
    called_tasks = []

    async def mock_execute_action_with_retry(task, session):
        nonlocal call_count
        nonlocal called_tasks
        call_count += 1
        called_tasks.append(task)
        session.get_task_status(task).mark_as_completed()
        return None

    with patch(
        "zrb.task.base.execution.execute_action_with_retry",
        new=Mock(side_effect=mock_execute_action_with_retry),
    ):
        await task1.exec_chain(session)

        # execute_action_with_retry should be called for task2 and task3,
        # but not for task1
        assert call_count == 2
        assert task2 in called_tasks
        assert task3 in called_tasks
        assert session.get_task_status(task1).is_skipped
        assert session.get_task_status(task2).is_completed
        assert session.get_task_status(task3).is_completed

