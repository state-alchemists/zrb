from zrb.task.cmd_task import CmdTask
import pathlib
import os


def test_simple_with_no_error():
    cmd_task = CmdTask(
        name='simple-no-error',
        cmd='echo hello'
    )
    main_loop = cmd_task.create_main_loop()
    result = main_loop()
    assert result.output == 'hello'


def test_simple_with_error():
    cmd_task = CmdTask(
        name='simple-error',
        cmd='forbidden command'
    )
    main_loop = cmd_task.create_main_loop()
    is_error: bool = False
    try:
        main_loop()
    except Exception:
        is_error = True
    assert is_error


def test_multiline_cmd():
    cmd_task = CmdTask(
        name='simple-no-error',
        cmd=[
            'echo hello',
            'echo hello again',
        ]
    )
    main_loop = cmd_task.create_main_loop()
    result = main_loop()
    assert result.output == '\n'.join(['hello', 'hello again'])


def test_cmd_path():
    dir_path = pathlib.Path(__file__).parent.absolute()
    cmd_task = CmdTask(
        name='simple-no-error',
        cmd_path=os.path.join(dir_path, 'templates', 'hello.sh')
    )
    main_loop = cmd_task.create_main_loop()
    result = main_loop()
    assert result.output == 'Hello, World!'


def test_upstream_with_no_error():
    upstream_task = CmdTask(
        name='upstream-no-error',
        cmd='echo upstream'
    )
    cmd_task = CmdTask(
        name='simple-no-error',
        cmd='echo hello',
        upstreams=[upstream_task]
    )
    main_loop = cmd_task.create_main_loop()
    result = main_loop()
    assert result.output == 'hello'


def test_upstream_with_error():
    upstream_task = CmdTask(
        name='upstream-error',
        cmd='forbidden command'
    )
    cmd_task = CmdTask(
        name='simple-no-error',
        cmd='echo hello',
        upstreams=[upstream_task]
    )
    main_loop = cmd_task.create_main_loop()
    is_error: bool = False
    try:
        main_loop()
    except Exception:
        is_error = True
    assert is_error


def test_diamond_upstream():
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
    main_loop = cmd_task.create_main_loop()
    result = main_loop()
    assert result.output == 'hello'


def test_checker_with_no_error():
    checker = CmdTask(
        name='check',
        cmd='echo checked'
    )
    cmd_task = CmdTask(
        name='simple-no-error',
        cmd='echo hello',
        checkers=[checker]
    )
    main_loop = cmd_task.create_main_loop()
    result = main_loop()
    assert result.output == 'hello'


def test_checker_with_error():
    checker = CmdTask(
        name='check',
        cmd='forbidden command'
    )
    cmd_task = CmdTask(
        name='simple-no-error',
        cmd='echo hello',
        checkers=[checker]
    )
    main_loop = cmd_task.create_main_loop()
    is_error: bool = False
    try:
        main_loop()
    except Exception:
        is_error = True
    assert is_error


def test_long_output():
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
    main_loop = cmd_task.create_main_loop()
    result = main_loop()
    assert result.output == '\n'.join(['3', '4', '5'])
