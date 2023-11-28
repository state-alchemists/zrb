from zrb.task.task import Task
from zrb.task.cmd_task import CmdTask
from zrb.task_env.env import Env
from zrb.task_env.env_file import EnvFile
from zrb.task_input.str_input import StrInput
import os
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


def test_task_with_should_execute_equal_to_false():
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


def test_task_with_input():
    def _run(*args, **kwargs) -> str:
        name = kwargs['name']
        favorite_drink = kwargs['favorite_drink']
        return f'hello {name}, your favorite drink is {favorite_drink}'
    task = Task(
        name='hello-name',
        inputs=[
            StrInput(name='name'),
            StrInput(name='favorite-drink')
        ],
        run=_run,
        retry=0
    )
    function = task.to_function()
    result = function(name='Dumbledore', favorite_drink='Elixir')
    assert result == 'hello Dumbledore, your favorite drink is Elixir'


def test_task_with_default_input():
    def _run(*args, **kwargs) -> str:
        name = kwargs['name']
        favorite_drink = kwargs['favorite_drink']
        return f'hello {name}, your favorite drink is {favorite_drink}'
    task = Task(
        name='hello-name',
        inputs=[
            StrInput(name='name', default='Nicholas Flamel'),
            StrInput(name='favorite-drink', default='Elixir')
        ],
        run=_run,
        retry=0
    )
    function = task.to_function()
    result = function()
    assert result == 'hello Nicholas Flamel, your favorite drink is Elixir'


def test_task_with_templated_input_without_kwarg():
    def _run(*args, **kwargs) -> str:
        name = kwargs['name']
        alias = kwargs['alias']
        return f'hello {name}, aka {alias}'
    task = Task(
        name='hello-name',
        inputs=[
            StrInput(name='name', default='Nicholas Flamel'),
            StrInput(name='alias', default='{{input.name}}')
        ],
        run=_run,
        retry=0
    )
    function = task.to_function()
    result = function()
    assert result == 'hello Nicholas Flamel, aka Nicholas Flamel'


def test_task_with_templated_input_and_partial_kwarg():
    def _run(*args, **kwargs) -> str:
        name = kwargs['name']
        alias = kwargs['alias']
        return f'hello {name}, aka {alias}'
    task = Task(
        name='hello-name',
        inputs=[
            StrInput(name='name', default='Nicholas Flamel'),
            StrInput(name='alias', default='{{input.name}}')
        ],
        run=_run,
        retry=0
    )
    function = task.to_function()
    result = function(name='Alchemist')
    assert result == 'hello Alchemist, aka Alchemist'


def test_task_with_templated_input():
    def _run(*args, **kwargs) -> str:
        name = kwargs['name']
        alias = kwargs['alias']
        return f'hello {name}, aka {alias}'
    task = Task(
        name='hello-name',
        inputs=[
            StrInput(name='name', default='Nicholas Flamel'),
            StrInput(name='alias', default='{{input.name}}')
        ],
        run=_run,
        retry=0
    )
    # Name and alias provided
    function = task.to_function()
    result = function(name='Nicholas Flamel', alias='Alchemist')
    assert result == 'hello Nicholas Flamel, aka Alchemist'


def test_task_with_templated_env():
    def _run(*args, **kwargs) -> str:
        task: Task = kwargs.get('_task')
        env_map = task.get_env_map()
        return env_map.get('ZRB_TEST_TASK_ENV_2')
    task = Task(
        name='templated-env',
        envs=[
            Env(name='ZRB_TEST_TASK_ENV_1', default='Elixir'),
            Env(
                name='ZRB_TEST_TASK_ENV_2',
                default='{{env.ZRB_TEST_TASK_ENV_1}} of immortality'
            )
        ],
        run=_run,
        retry=0
    )
    function = task.to_function()
    if 'ZRB_TEST_TASK_ENV_1' in os.environ:
        del os.environ['ZRB_TEST_TASK_ENV_1']
    if 'ZRB_TEST_TASK_ENV_2' in os.environ:
        del os.environ['ZRB_TEST_TASK_ENV_2']
    result = function()
    assert result == 'Elixir of immortality'


def test_task_with_env_file():
    def _run(*args, **kwargs) -> str:
        task: Task = kwargs.get('_task')
        env_map = task.get_env_map()
        return env_map.get('COLOR')
    env_file = os.path.join(os.path.dirname(__file__), 'test_task.env')
    task = Task(
        name='env-file',
        env_files=[EnvFile(env_file=env_file)],
        run=_run,
        retry=0
    )
    function = task.to_function()
    result = function()
    assert result == 'blue'


def test_task_with_env_file_and_prefix():
    def _run(*args, **kwargs) -> str:
        task: Task = kwargs.get('_task')
        env_map = task.get_env_map()
        return env_map.get('COLOR')
    env_file = os.path.join(os.path.dirname(__file__), 'test_task.env')
    task = Task(
        name='env-file-prefixed',
        env_files=[
            EnvFile(
                env_file=env_file, prefix='ZRB_TEST_TASK_WITH_ENV_AND_PREFIX'
            )
        ],
        run=_run,
        retry=0
    )
    function = task.to_function()
    if 'ZRB_TEST_TASK_WITH_ENV_AND_PREFIX_COLOR' in os.environ:
        del os.environ['ZRB_TEST_TASK_WITH_ENV_AND_PREFIX_COLOR']
    os.environ['ZRB_TEST_TASK_WITH_ENV_AND_PREFIX_COLOR'] = 'red'
    result = function()
    assert result == 'red'
    del os.environ['ZRB_TEST_TASK_WITH_ENV_AND_PREFIX_COLOR']


def test_task_env_with_none_as_os_name():
    '''
    When env exist, it should override env_file
    '''
    def _run(*args, **kwargs) -> str:
        task: Task = kwargs.get('_task')
        env_map = task.get_env_map()
        return env_map.get('COLOR')
    env_file = os.path.join(os.path.dirname(__file__), 'test_task.env')
    task = Task(
        name='env-file-prefixed',
        env_files=[
            EnvFile(env_file=env_file, prefix='ZRB_TEST_TASK_OS_NAME_NONE')
        ],
        envs=[Env(name='COLOR', os_name=None, default='green')],
        run=_run,
        retry=0
    )
    function = task.to_function()
    if 'ZRB_TEST_TASK_OS_NAME_NONE_COLOR' in os.environ:
        del os.environ['ZRB_TEST_TASK_OS_NAME_NONE_COLOR']
    if 'COLOR' in os.environ:
        del os.environ['COLOR']
    os.environ['ZRB_TEST_TASK_OS_NAME_NONE_COLOR'] = 'red'
    os.environ['COLOR'] = 'cyan'
    result = function()
    assert result == 'cyan'
    del os.environ['ZRB_TEST_TASK_OS_NAME_NONE_COLOR']
    del os.environ['COLOR']


def test_task_env_with_empty_string_as_os_name():
    '''
    When env exist, it should override env_file,
    If env has empty os_name, the default value should always be used.
    '''
    def _run(*args, **kwargs) -> str:
        task: Task = kwargs.get('_task')
        env_map = task.get_env_map()
        return env_map.get('COLOR')
    env_file = os.path.join(os.path.dirname(__file__), 'test_task.env')
    task = Task(
        name='env-file-prefixed',
        env_files=[
            EnvFile(env_file=env_file, prefix='ZRB_TEST_TASK_OS_NAME_EMPTY')
        ],
        envs=[Env(name='COLOR', os_name='', default='green')],
        run=_run,
        retry=0
    )
    function = task.to_function()
    if 'ZRB_TEST_TASK_OS_NAME_EMPTY_COLOR' in os.environ:
        del os.environ['ZRB_TEST_TASK_OS_NAME_EMPTY_COLOR']
    if 'COLOR' in os.environ:
        del os.environ['COLOR']
    os.environ['ZRB_TEST_TASK_OS_NAME_EMPTY_COLOR'] = 'red'
    os.environ['COLOR'] = 'cyan'
    result = function()
    assert result == 'green'
    del os.environ['ZRB_TEST_TASK_OS_NAME_EMPTY_COLOR']
    del os.environ['COLOR']


def test_task_redeclared_env():
    '''
    When env exist, it should override env_file,
    If two env has the same name, the later should override the first one
    '''
    def _run(*args, **kwargs) -> str:
        task: Task = kwargs.get('_task')
        env_map = task.get_env_map()
        return env_map.get('COLOR')
    env_file = os.path.join(os.path.dirname(__file__), 'test_task.env')
    task = Task(
        name='env-file-prefixed',
        env_files=[EnvFile(env_file=env_file, prefix='ZRB_TEST_TASK')],
        envs=[
            Env(name='COLOR', os_name='', default='green'),
            Env(name='COLOR', os_name='', default='yellow')
        ],
        run=_run,
        retry=0
    )
    function = task.to_function()
    result = function()
    assert result == 'yellow'


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


def test_task_with_duplicated_input_name():
    task = Task(
        name='task',
        inputs=[
            StrInput(name='name', default='articuno'),
            StrInput(name='name', default='zapdos'),
            StrInput(name='name', default='moltres'),
        ],
        run=lambda *args, **kwargs: kwargs.get('name')
    )
    function = task.to_function()
    result = function()
    assert result == 'moltres'


def test_upstream_task_with_the_same_input_name():
    task_upstream = Task(
        name='task-upstream',
        inputs=[
            StrInput(name='name', default='articuno')
        ],
        run=lambda *args, **kwargs: kwargs.get('name')
    )
    task = Task(
        name='task',
        inputs=[
            StrInput(name='name', default='zapdos')
        ],
        upstreams=[task_upstream],
        run=lambda *args, **kwargs: kwargs.get('name')
    )
    function = task.to_function()
    result = function()
    assert result == 'zapdos'


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


def test_callable_as_task_should_execute():
    # should execute should accept executable
    task = Task(
        name='task',
        should_execute=lambda *args, **kwargs: True,
        run=lambda *args, **kwargs: 'articuno'
    )
    function = task.to_function()
    result = function()
    assert result == 'articuno'


def test_consistent_execution_id():
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
