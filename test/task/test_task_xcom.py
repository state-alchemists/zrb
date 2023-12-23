from zrb.task.decorator import python_task
from zrb.task.cmd_task import CmdTask
from zrb.task.task import Task


def test_set_xcom():
    set_xcom_cmd = CmdTask(
        name='set-xcom-cmd',
        cmd='echo "hi{{task.set_xcom("one", "ichi")}}"'
    )

    @python_task(name='set-xcom-py')
    def set_xcom_py(*args, **kwargs):
        task: Task = kwargs.get('_task')
        task.set_xcom('two', 'ni')

    get_xcom_cmd = CmdTask(
        name='get-xcom-cmd',
        upstreams=[set_xcom_cmd, set_xcom_py],
        cmd=[
            'echo {{task.get_xcom("one")}}',
            'echo {{task.get_xcom("two")}}',
        ]
    )

    @python_task(
        name='get-xcom-py',
        upstreams=[set_xcom_cmd, set_xcom_py],
    )
    def get_xcom_py(*args, **kwargs):
        task: Task = kwargs.get('_task')
        return '\n'.join([
            task.get_xcom("one"),
            task.get_xcom("two"),
        ])

    test_xcom = Task(
        name='test-xcom',
        upstreams=[get_xcom_cmd, get_xcom_py],
        return_upstream_result=True
    )
    fn = test_xcom.to_function()
    result = fn()
    assert len(result) == 2
    assert result[0].output == 'ichi\nni'
    assert result[1] == 'ichi\nni'


def test_get_return_value_as_xcom():
    hello_cmd = CmdTask(
        name='hello-cmd',
        cmd='echo hello-cmd',
    )

    @python_task(
        name='hello-py'
    )
    def hello_py(*args, **kwargs):
        return 'hello-py'

    hello = CmdTask(
        name='hello',
        upstreams=[hello_cmd, hello_py],
        cmd=[
            'echo {{task.get_xcom("hello-cmd")}}',
            'echo {{task.get_xcom("hello-py")}}',
        ],
    )
    fn = hello.to_function()
    result = fn()
    assert result.output == 'hello-cmd\nhello-py'
