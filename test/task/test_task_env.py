from zrb.task.task import Task
from zrb.task_env.env import Env
from zrb.task_env.env_file import EnvFile
import os


def test_task_env_with_jinja_value():
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


def test_task_env_with_should_not_be_rendered_jinja_value():
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
                default='{{env.ZRB_TEST_TASK_ENV_1}} of immortality',
                should_render=False
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
    assert result == '{{env.ZRB_TEST_TASK_ENV_1}} of immortality'


def test_task_env_with_none_as_os_name():
    '''
    When env exist, it should override env_file
    '''
    def _run(*args, **kwargs) -> str:
        task: Task = kwargs.get('_task')
        env_map = task.get_env_map()
        return env_map.get('COLOR')
    env_file = os.path.join(
        os.path.dirname(__file__), 'test_task_env_file.env'
    )
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
    env_file = os.path.join(
        os.path.dirname(__file__), 'test_task_env_file.env'
    )
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


def test_task_duplicate_env():
    '''
    When env exist, it should override env_file,
    If two env has the same name, the later should override the first one
    '''
    def _run(*args, **kwargs) -> str:
        task: Task = kwargs.get('_task')
        env_map = task.get_env_map()
        return env_map.get('COLOR')
    env_file = os.path.join(
        os.path.dirname(__file__), 'test_task_env_file.env'
    )
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
