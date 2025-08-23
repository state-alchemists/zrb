import asyncio
from unittest.mock import MagicMock, patch

from zrb.context.any_context import AnyContext
from zrb.session.any_session import AnySession
from zrb.task.any_task import AnyTask
from zrb.task.base_task import BaseTask

# Mock dependencies
mock_any_session = MagicMock(spec=AnySession)
mock_any_context = MagicMock(spec=AnyContext)
mock_any_task = MagicMock(spec=AnyTask)


def test_base_task_init():
    task = BaseTask(name="test_task")
    assert task.name == "test_task"
    assert task.color is None
    assert task.icon is None
    assert task.description == "test_task"
    assert task.cli_only is False
    assert task._inputs is None
    assert task._envs is None
    assert task._retries == 2
    assert task._retry_period == 0
    assert task._upstreams is None
    assert task._fallbacks is None
    assert task._successors is None
    assert task._readiness_checks is None
    assert task._readiness_check_delay == 0.5
    assert task._readiness_check_period == 5
    assert task._readiness_failure_threshold == 1
    assert task._readiness_timeout == 60
    assert task._monitor_readiness is False
    assert task._execute_condition is True
    assert task._action is None


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

    task._fallbacks = mock_any_task
    assert task.fallbacks == [mock_any_task]

    task._fallbacks = [mock_any_task, mock_any_task]
    assert task.fallbacks == [mock_any_task, mock_any_task]


def test_base_task_append_fallback():
    task = BaseTask(name="test_task")
    task.append_fallback(mock_any_task)
    assert task._fallbacks == [mock_any_task]

    task.append_fallback([mock_any_task, mock_any_task])
    assert task._fallbacks == [mock_any_task]  # Ensure no duplicates

    mock_another_task = MagicMock(spec=AnyTask)
    task.append_fallback(mock_another_task)
    assert task._fallbacks == [mock_any_task, mock_another_task]


def test_base_task_successors_property():
    task = BaseTask(name="test_task")
    assert task.successors == []

    task._successors = mock_any_task
    assert task.successors == [mock_any_task]

    task._successors = [mock_any_task, mock_any_task]
    assert task.successors == [mock_any_task, mock_any_task]


def test_base_task_append_successor():
    task = BaseTask(name="test_task")
    task.append_successor(mock_any_task)
    assert task._successors == [mock_any_task]

    task.append_successor([mock_any_task, mock_any_task])
    assert task._successors == [mock_any_task]  # Ensure no duplicates

    mock_another_task = MagicMock(spec=AnyTask)
    task.append_successor(mock_another_task)
    assert task._successors == [mock_any_task, mock_another_task]


def test_base_task_readiness_checks_property():
    task = BaseTask(name="test_task")
    assert task.readiness_checks == []

    task._readiness_checks = mock_any_task
    assert task.readiness_checks == [mock_any_task]

    task._readiness_checks = [mock_any_task, mock_any_task]
    assert task.readiness_checks == [mock_any_task, mock_any_task]


def test_base_task_append_readiness_check():
    task = BaseTask(name="test_task")
    task.append_readiness_check(mock_any_task)
    assert task._readiness_checks == [mock_any_task]

    task.append_readiness_check([mock_any_task, mock_any_task])
    assert task._readiness_checks == [mock_any_task]  # Ensure no duplicates

    mock_another_task = MagicMock(spec=AnyTask)
    task.append_readiness_check(mock_another_task)
    assert task._readiness_checks == [mock_any_task, mock_another_task]


def test_base_task_upstreams_property():
    task = BaseTask(name="test_task")
    assert task.upstreams == []

    task._upstreams = mock_any_task
    assert task.upstreams == [mock_any_task]

    task._upstreams = [mock_any_task, mock_any_task]
    assert task.upstreams == [mock_any_task, mock_any_task]


def test_base_task_append_upstream():
    task = BaseTask(name="test_task")
    task.append_upstream(mock_any_task)
    assert task._upstreams == [mock_any_task]

    task.append_upstream([mock_any_task, mock_any_task])
    assert task._upstreams == [mock_any_task]  # Ensure no duplicates

    mock_another_task = MagicMock(spec=AnyTask)
    task.append_upstream(mock_another_task)
    assert task._upstreams == [mock_any_task, mock_another_task]


@patch("zrb.task.base_task.build_task_context")
def test_base_task_get_ctx(mock_build_task_context):
    task = BaseTask(name="test_task")
    task.get_ctx(mock_any_session)
    mock_build_task_context.assert_called_once_with(task, mock_any_session)


@patch("asyncio.run")
@patch("zrb.task.base_task.run_and_cleanup")
def test_base_task_run(mock_run_and_cleanup, mock_asyncio_run):
    task = BaseTask(name="test_task")
    mock_awaitable = MagicMock()
    mock_run_and_cleanup.return_value = mock_awaitable

    task.run(session=mock_any_session, str_kwargs={"key": "value"})

    mock_run_and_cleanup.assert_called_once_with(
        task, session=mock_any_session, str_kwargs={"key": "value"}, kwargs=None
    )
    # Assert that asyncio.run was called with a coroutine object
    mock_asyncio_run.assert_called_once()
    called_with_arg = mock_asyncio_run.call_args[0][0]
    assert asyncio.iscoroutine(called_with_arg)


@patch("zrb.task.base_task.run_task_async")
def test_base_task_async_run(mock_run_task_async):
    async def run_async_test():
        task = BaseTask(name="test_task")
        await task.async_run(session=mock_any_session, str_kwargs={"key": "value"})
        mock_run_task_async.assert_called_once_with(
            task,
            session=mock_any_session,
            str_kwargs={"key": "value"},
            kwargs=None,
        )

    asyncio.run(run_async_test())


@patch("zrb.task.base_task.execute_root_tasks")
def test_base_task_exec_root_tasks(mock_execute_root_tasks):
    async def run_async_test():
        task = BaseTask(name="test_task")
        await task.exec_root_tasks(mock_any_session)
        mock_execute_root_tasks.assert_called_once_with(task, mock_any_session)

    asyncio.run(run_async_test())


@patch("zrb.task.base_task.execute_task_chain")
def test_base_task_exec_chain(mock_execute_task_chain):
    async def run_async_test():
        task = BaseTask(name="test_task")
        await task.exec_chain(mock_any_session)
        mock_execute_task_chain.assert_called_once_with(task, mock_any_session)

    asyncio.run(run_async_test())


@patch("zrb.task.base_task.execute_task_action")
def test_base_task_exec(mock_execute_task_action):
    async def run_async_test():
        task = BaseTask(name="test_task")
        await task.exec(mock_any_session)
        mock_execute_task_action.assert_called_once_with(task, mock_any_session)

    asyncio.run(run_async_test())


@patch("zrb.task.base_task.run_default_action")
def test_base_task_exec_action(mock_run_default_action):
    async def run_async_test():
        task = BaseTask(name="test_task")
        await task._exec_action(mock_any_context)
        mock_run_default_action.assert_called_once_with(task, mock_any_context)

    asyncio.run(run_async_test())
