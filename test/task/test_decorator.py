from zrb.task.decorator import python_task


def test_task_with_decorated_runner():
    @python_task(
        name='hello'
    )
    async def hello(*args, **kwargs) -> str:
        return 'hello'

    function = hello.to_function()
    result = function()
    assert result == 'hello'
