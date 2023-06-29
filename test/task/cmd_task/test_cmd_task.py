from zrb.task.cmd_task import CmdTask
from zrb.task_input.str_input import StrInput
import pathlib
import os


def test_cmd_task():
    cmd_task = CmdTask(
        name='simple-no-error',
        cmd='echo hello'
    )
    function = cmd_task.to_function()
    result = function()
    assert result.output == 'hello'


def test_cmd_task_with_error():
    cmd_task = CmdTask(
        name='simple-error',
        cmd='forbidden command'
    )
    function = cmd_task.to_function()
    is_error: bool = False
    try:
        function()
    except Exception:
        is_error = True
    assert is_error


def test_cmd_task_with_multiline_command():
    cmd_task = CmdTask(
        name='simple-no-error',
        cmd=[
            'echo hello',
            'echo hello again',
        ]
    )
    function = cmd_task.to_function()
    result = function()
    assert result.output == '\n'.join(['hello', 'hello again'])


def test_cmd_task_with_cmd_path():
    dir_path = pathlib.Path(__file__).parent.absolute()
    cmd_task = CmdTask(
        name='simple-no-error',
        cmd_path=os.path.join(dir_path, 'templates', 'hello.sh')
    )
    function = cmd_task.to_function()
    result = function()
    assert result.output == 'Hello, World!'


def test_cmd_task_with_upstream_with_no_error():
    upstream_task = CmdTask(
        name='upstream-no-error',
        cmd='echo upstream'
    )
    cmd_task = CmdTask(
        name='simple-no-error',
        cmd='echo hello',
        upstreams=[upstream_task]
    )
    function = cmd_task.to_function()
    result = function()
    assert result.output == 'hello'


def test_cmd_task_with_upstream_with_error():
    upstream_task = CmdTask(
        name='upstream-error',
        cmd='forbidden command'
    )
    cmd_task = CmdTask(
        name='simple-no-error',
        cmd='echo hello',
        upstreams=[upstream_task]
    )
    function = cmd_task.to_function()
    is_error: bool = False
    try:
        function()
    except Exception:
        is_error = True
    assert is_error


def test_cmd_task_with_upstream_containing_inputs():
    upstream = CmdTask(
        name='ask-name',
        inputs=[
            StrInput(name='name')
        ]
    )
    cmd_task = CmdTask(
        name='hello',
        cmd='echo hello {{input.name}}',
        upstreams=[upstream]
    )
    function = cmd_task.to_function()
    result = function(name='Dumbledore')
    assert result.output == 'hello Dumbledore'


def test_cmd_task_with_diamond_upstream():
    upstream_0 = CmdTask(
        name='upstream-no-error',
        cmd='echo upstream 0'
    )
    upstream_1 = CmdTask(
        name='upstream-no-error',
        cmd='echo upstream 1',
        upstreams=[upstream_0]
    )
    upstream_2 = CmdTask(
        name='upstream-no-error',
        cmd='echo upstream 2',
        upstreams=[upstream_0]
    )
    cmd_task = CmdTask(
        name='simple-no-error',
        cmd='echo hello',
        upstreams=[upstream_1, upstream_2]
    )
    function = cmd_task.to_function()
    result = function()
    assert result.output == 'hello'


def test_cmd_task_with_checker_with_no_error():
    checker = CmdTask(
        name='check',
        cmd='echo checked'
    )
    cmd_task = CmdTask(
        name='simple-no-error',
        cmd='echo hello',
        checkers=[checker]
    )
    function = cmd_task.to_function()
    result = function()
    assert result.output == 'hello'


def test_cmd_task_with_checker_with_error():
    checker = CmdTask(
        name='check',
        cmd='forbidden command'
    )
    cmd_task = CmdTask(
        name='simple-no-error',
        cmd='echo hello',
        checkers=[checker]
    )
    function = cmd_task.to_function()
    is_error: bool = False
    try:
        function()
    except Exception:
        is_error = True
    assert is_error


def test_cmd_task_with_long_output():
    cmd_task = CmdTask(
        name='long-output',
        cmd=[
            'echo 1',
            'echo 2',
            'echo 3',
            'echo 4',
            'echo 5',
        ],
        max_output_line=3,
    )
    function = cmd_task.to_function()
    result = function()
    assert result.output == '\n'.join(['3', '4', '5'])
