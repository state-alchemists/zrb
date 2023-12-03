from zrb.task.task import Task
from zrb.task.parallel import Parallel


def test_task_shift_right_operator():
    task_1 = Task(name='task-1')
    task_2 = Task(name='task-2')
    task_3 = Task(name='task-3')
    task_4 = Task(name='task-4')
    # define DAG
    task_1 >> task_2 >> task_3 >> task_4
    # test 1
    upstream_1 = task_1._get_upstreams()
    assert len(upstream_1) == 0
    # test 2
    upstream_2 = task_2._get_upstreams()
    assert len(upstream_2) == 1
    assert upstream_2[0] == task_1
    # test 3
    upstream_3 = task_3._get_upstreams()
    assert len(upstream_3) == 1
    assert upstream_3[0] == task_2
    # test 4
    upstream_4 = task_4._get_upstreams()
    assert len(upstream_4) == 1
    assert upstream_4[0] == task_3


def test_task_shift_right_operator_with_parallel():
    task_1 = Task(name='task-1')
    task_2 = Task(name='task-2')
    task_3 = Task(name='task-3')
    task_4 = Task(name='task-4')
    task_5 = Task(name='task-5')
    task_6 = Task(name='task-6')
    # define DAG
    task_1 >> Parallel(task_2, task_3) >> Parallel(task_4, task_5) >> task_6
    # test 1
    upstream_1 = task_1._get_upstreams()
    assert len(upstream_1) == 0
    # test 2
    upstream_2 = task_2._get_upstreams()
    assert len(upstream_2) == 1
    assert upstream_2[0] == task_1
    # test 3
    upstream_3 = task_3._get_upstreams()
    assert len(upstream_3) == 1
    assert upstream_3[0] == task_1
    # test 4
    upstream_4 = task_4._get_upstreams()
    assert len(upstream_4) == 2
    assert upstream_4[0] == task_2
    assert upstream_4[1] == task_3
    # test 5
    upstream_5 = task_5._get_upstreams()
    assert len(upstream_5) == 2
    assert upstream_5[0] == task_2
    assert upstream_5[1] == task_3
    # test 6
    upstream_6 = task_6._get_upstreams()
    assert len(upstream_6) == 2
    assert upstream_6[0] == task_4
    assert upstream_6[1] == task_5
