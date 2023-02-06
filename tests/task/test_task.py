from zrb.task.task import Task
from zrb.task_input.str_input import StrInput


def test_task_with_no_runner():
    task = Task(
        name='simple-no-error',
    )
    main_loop = task.create_main_loop()
    result = main_loop()
    assert result


def test_task_with_predefined_runner():
    def _run(*args, **kwargs) -> str:
        return 'hello'
    task = Task(
        name='hello',
        runner=_run
    )
    main_loop = task.create_main_loop()
    result = main_loop()
    assert result == 'hello'


def test_task_with_decorated_runner():
    task = Task(
        name='hello',
    )

    @task.runner
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
        runner=_run
    )
    # should throw error when add decorated runner
    # to a task with pre-existing runner
    is_error = False
    try:
        @task.runner
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
        runner=_run
    )
    main_loop = task.create_main_loop()
    result = main_loop(name='Dumbledore', favorite_drink='Elixir')
    assert result == 'hello Dumbledore, your favorite drink is Elixir'
