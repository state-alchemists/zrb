from zrb.task.task import Task
from zrb.task_input.str_input import StrInput
import asyncio


def test_task_with_no_runner():
    task = Task(
        name='simple-no-error',
        retry=0
    )
    function = task.to_function()
    result = function()
    assert result is None


def test_task_with_predefined_runner():
    def _run(*args, **kwargs) -> str:
        return 'hello'
    task = Task(
        name='hello',
        run=_run,
        retry=0
    )
    function = task.to_function()
    result = function()
    assert result == 'hello'


def test_should_not_executed_task():
    def _run(*args, **kwargs) -> str:
        return 'hello'
    task = Task(
        name='hello',
        run=_run,
        retry=0,
        should_execute=False
    )
    function = task.to_function()
    result = function()
    assert result is None


def test_task_returning_upstream_result():
    task_upstream_1 = Task(
        name='task-upstream-1',
        run=lambda *args, **kwargs: 'articuno'
    )
    task_upstream_2 = Task(
        name='task-upstream-2',
        run=lambda *args, **kwargs: 'zapdos'
    )
    task_upstream_3 = Task(
        name='task-upstream-3',
        run=lambda *args, **kwargs: 'moltres'
    )
    task = Task(
        name='task',
        upstreams=[
            task_upstream_1, task_upstream_2, task_upstream_3
        ],
        return_upstream_result=True
    )
    function = task.to_function()
    result = function()
    assert len(result) == 3
    assert 'articuno' in result
    assert 'zapdos' in result
    assert 'moltres' in result


def test_task_to_async_function():
    task = Task(
        name='task',
        inputs=[
            StrInput(name='name', default='zapdos')
        ],
        run=lambda *args, **kwargs: kwargs.get('name')
    )
    function = task.to_function(is_async=True)
    result = asyncio.run(function())
    assert result == 'zapdos'


def test_task_function_should_accept_kwargs_args():
    task = Task(
        name='task',
        run=lambda *args, **kwargs: args[0]
    )
    function = task.to_function()
    # _args keyword argument should be treated as *args
    result = function(_args=['moltres'])
    assert result == 'moltres'


def test_callable_as_task_should_execute_value():
    # should execute should accept executable
    task = Task(
        name='task',
        should_execute=lambda *args, **kwargs: True,
        run=lambda *args, **kwargs: 'articuno'
    )
    function = task.to_function()
    result = function()
    assert result == 'articuno'
