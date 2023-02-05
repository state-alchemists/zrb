from zrb.task.task import Task
from zrb.task_input.str_input import StrInput


def test_task_with_no_runner():
    task = Task(
        name='simple-no-error',
    )
    main_loop = task.create_main_loop()
    result = main_loop()
    assert result


def test_task_with_runner():
    task = Task(
        name='hello',
    )

    @task.runner
    def _run(*args, **kwargs) -> str:
        return 'hello'

    main_loop = task.create_main_loop()
    result = main_loop()
    assert result == 'hello'


def test_task_with_input():
    task = Task(
        name='hello-name',
        inputs=[
            StrInput(name='name'),
            StrInput(name='favorite-drink')
        ]
    )

    @task.runner
    def _run(*args, **kwargs) -> str:
        name = kwargs['name']
        favorite_drink = kwargs['favorite_drink']
        return f'hello {name}, your favorite drink is {favorite_drink}'

    main_loop = task.create_main_loop()
    result = main_loop(name='Dumbledore', favorite_drink='Elixir')
    assert result == 'hello Dumbledore, your favorite drink is Elixir'
