from zrb.task.task import Task
from zrb.task.cmd_task import CmdTask


def test_task_execution_id_cannot_be_set_twice():
    task = Task(
        name='task',
        run=lambda *args, **kwargs: kwargs.get('_task').get_execution_id()
    )
    task._set_execution_id('execution_id_1')
    task._set_execution_id('execution_id_2')
    task._set_execution_id('execution_id_3')
    function = task.to_function()
    result = function()
    assert result == 'execution_id_1'


def test_consistent_task_upstream_execution_id():
    task_upstream_1 = Task(
        name='task-upstream-1',
        run=lambda *args, **kwargs: kwargs.get('_task').get_execution_id()
    )
    task_upstream_2 = CmdTask(
        name='task-upstream-2',
        cmd='echo $_ZRB_EXECUTION_ID'
    )
    task = Task(
        name='task',
        upstreams=[
            task_upstream_1, task_upstream_2
        ],
        return_upstream_result=True
    )
    function = task.to_function()
    result = function()
    assert result[0] == result[1].output
