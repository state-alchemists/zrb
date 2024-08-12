from typing import Any
from zrb.task.decorator import python_task
from zrb.task.any_task import AnyTask
from zrb.task.cmd_task import CmdTask


def create_on_failed(logs: list[str]):
    def on_failed(task: AnyTask, is_last_attempt: bool, exception: Exception):
        task_name = task.get_name()
        if is_last_attempt:
            logs.append(f'{task_name} failed for good')
            return
        logs.append(f'{task_name} failed')
    return on_failed


def create_fallback_task(task_name: str, logs: list[str]):
    @python_task(
        name="fallback",
        retry=0
    )
    def fallback(*args: Any, **kwargs: Any):
        logs.append(f'{task_name} fallback')
    return fallback


def test_failure_and_fallback():
    logs: list[str] = []
    task_1 = CmdTask(
        name='task1',
        on_failed=create_on_failed(logs),
        fallbacks=[create_fallback_task('task1', logs)],
        cmd="echo hello"
    )
    task_2 = CmdTask(
        name='task2',
        on_failed=create_on_failed(logs),
        fallbacks=[create_fallback_task('task2', logs)],
        retry=1,
        cmd="sleep 1 && exit 1"
    )
    task_3 = CmdTask(
        name='task3',
        on_failed=create_on_failed(logs),
        fallbacks=[create_fallback_task('task3', logs)],
        cmd="sleep 4 && echo hello"
    )
    task = CmdTask(
        name="task",
        upstreams=[task_1, task_2, task_3],
        cmd="echo hello"
    )
    function = task.to_function()
    is_error = False
    try:
        function()
    except Exception:
        is_error = True
    assert is_error
    assert len(logs) == 5
    'task2 failed' in logs
    'task2 failed for good' in logs
    'task2 fallback' in logs
    'task3 failed for good' in logs
    'task3 fallback' in logs

