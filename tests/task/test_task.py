from zrb.task.task import Task
from zrb.task_env.env import Env
from zrb.task_input.str_input import StrInput


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


def test_task_with_decorated_runner():
    task = Task(
        name='hello',
    )

    @task.should
    def _run(*args, **kwargs) -> str:
        return 'hello'

    main_loop = task.create_main_loop()
    result = main_loop()
    assert result == 'hello'


def test_task_with_predefined_and_decorated_runner():
    def _run(*args, **kwargs) -> str:
        return 'hello'
    task = Task(
        name='hello',
        run=_run,
        retry=0
    )
    # should throw error when add decorated runner
    # to a task with pre-existing runner
    is_error = False
    try:
        @task.should
        def _run(*args, **kwargs) -> str:
            return 'not-hello'
    except Exception:
        is_error = True
    assert is_error
    main_loop = task.create_main_loop()
    result = main_loop()
    assert result == 'hello'


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
        return env_map.get('__ZRB_TEST_ENV_2')
    task = Task(
        name='templated-env',
        envs=[
            Env(name='__ZRB_TEST_ENV_1', default='Elixir'),
            Env(
                name='__ZRB_TEST_ENV_2',
                default='{{env.__ZRB_TEST_ENV_1}} of immortality'
            )
        ],
        run=_run,
        retry=0
    )
    main_loop = task.create_main_loop()
    result = main_loop()
    assert result == 'Elixir of immortality'
