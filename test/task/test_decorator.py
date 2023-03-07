from zrb.task.decorator import python_task


def test_task_with_decorated_runner():
    @python_task(
        name='hello'
    )
    async def hello(*args, **kwargs) -> str:
        return 'hello'

    main_loop = hello.create_main_loop()
    result = main_loop()
    assert result == 'hello'
