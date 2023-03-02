from zrb.task.task import Task
from zrb.task_env.env import Env
from zrb.task_env.env_file import EnvFile
from zrb.task_input.str_input import StrInput
import os


def test_task_with_no_runner():
    task = Task(
        name='simple-no-error',
        retry=0
    )
    main_loop = task.create_main_loop()
    result = main_loop()
    assert result


def test_task_with_predefined_runner():
    def _run(*args, **kwargs) -> str:
        return 'hello'
    task = Task(
        name='hello',
        run=_run,
        retry=0
    )
    main_loop = task.create_main_loop()
    result = main_loop()
    assert result == 'hello'


def test_task_with_skip_execution():
    def _run(*args, **kwargs) -> str:
        return 'hello'
    task = Task(
        name='hello',
        run=_run,
        retry=0,
        skip_execution=True
    )
    main_loop = task.create_main_loop()
    result = main_loop()
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
    main_loop = task.create_main_loop()
    result = main_loop(name='Dumbledore', favorite_drink='Elixir')
    assert result == 'hello Dumbledore, your favorite drink is Elixir'


def test_task_with_templated_env():
    def _run(*args, **kwargs) -> str:
        task: Task = kwargs.get('_task')
        env_map = task.get_env_map()
        return env_map.get('ZRB_TEST_ENV_2')
    task = Task(
        name='templated-env',
        envs=[
            Env(name='ZRB_TEST_ENV_1', default='Elixir'),
            Env(
                name='ZRB_TEST_ENV_2',
                default='{{env.ZRB_TEST_ENV_1}} of immortality'
            )
        ],
        run=_run,
        retry=0
    )
    main_loop = task.create_main_loop()
    if 'ZRB_TEST_ENV_1' in os.environ:
        del os.environ['ZRB_TEST_ENV_1']
    if 'ZRB_TEST_ENV_2' in os.environ:
        del os.environ['ZRB_TEST_ENV_2']
    result = main_loop()
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
    main_loop = task.create_main_loop()
    if 'COLOR' in os.environ:
        del os.environ['COLOR']
    result = main_loop()
    assert result == 'blue'


def test_task_with_env_file_and_prefix():
    def _run(*args, **kwargs) -> str:
        task: Task = kwargs.get('_task')
        env_map = task.get_env_map()
        return env_map.get('COLOR')
    env_file = os.path.join(os.path.dirname(__file__), 'test_task.env')
    task = Task(
        name='env-file-prefixed',
        env_files=[EnvFile(env_file=env_file, prefix='ZRB_TEST')],
        run=_run,
        retry=0
    )
    main_loop = task.create_main_loop()
    if 'ZRB_TEST_COLOR' in os.environ:
        del os.environ['ZRB_TEST_COLOR']
    os.environ['ZRB_TEST_COLOR'] = 'red'
    result = main_loop()
    assert result == 'red'
    del os.environ['ZRB_TEST_COLOR']


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
        env_files=[EnvFile(env_file=env_file, prefix='ZRB_TEST')],
        envs=[Env(name='COLOR', os_name=None, default='green')],
        run=_run,
        retry=0
    )
    main_loop = task.create_main_loop()
    if 'ZRB_TEST_COLOR' in os.environ:
        del os.environ['ZRB_TEST_COLOR']
    if 'COLOR' in os.environ:
        del os.environ['COLOR']
    os.environ['ZRB_TEST_COLOR'] = 'red'
    os.environ['COLOR'] = 'cyan'
    result = main_loop()
    assert result == 'cyan'
    del os.environ['ZRB_TEST_COLOR']
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
        env_files=[EnvFile(env_file=env_file, prefix='ZRB_TEST')],
        envs=[Env(name='COLOR', os_name='', default='green')],
        run=_run,
        retry=0
    )
    main_loop = task.create_main_loop()
    if 'ZRB_TEST_COLOR' in os.environ:
        del os.environ['ZRB_TEST_COLOR']
    if 'COLOR' in os.environ:
        del os.environ['COLOR']
    os.environ['ZRB_TEST_COLOR'] = 'red'
    os.environ['COLOR'] = 'cyan'
    result = main_loop()
    assert result == 'green'
    del os.environ['ZRB_TEST_COLOR']
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
        env_files=[EnvFile(env_file=env_file, prefix='ZRB_TEST')],
        envs=[
            Env(name='COLOR', os_name='', default='green'),
            Env(name='COLOR', default='yellow')
        ],
        run=_run,
        retry=0
    )
    main_loop = task.create_main_loop()
    if 'ZRB_TEST_COLOR' in os.environ:
        del os.environ['ZRB_TEST_COLOR']
    if 'COLOR' in os.environ:
        del os.environ['COLOR']
    os.environ['ZRB_TEST_COLOR'] = 'red'
    os.environ['COLOR'] = 'cyan'
    result = main_loop()
    assert result == 'cyan'
    del os.environ['ZRB_TEST_COLOR']
    del os.environ['COLOR']

