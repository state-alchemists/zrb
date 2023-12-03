from zrb.task.task import Task


def test_consistent_task_shift_right_operator():
    result = []
    task_1 = Task(
        name='task-1',
        run=lambda *args, **kwargs: result.append(1)
    )
    task_2 = Task(
        name='task-2',
        run=lambda *args, **kwargs: result.append(2)
    )
    task_3 = Task(
        name='task-3',
        run=lambda *args, **kwargs: result.append(3)
    )
    task_4 = Task(
        name='task-4',
        run=lambda *args, **kwargs: result.append(4)
    )
    task_1 >> task_2 >> task_3 >> task_4
    function = task_4.to_function()
    function()
    assert result[0] == 1
    assert result[1] == 2
    assert result[2] == 3
    assert result[3] == 4
