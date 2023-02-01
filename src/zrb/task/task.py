from .base_task import BaseTask


class Task(BaseTask):
    '''
    Common Task.
    This task doesn't override any behavior of BaseTask.
    Thus, it is suitable to be used as wrapper.

    For example:
    ```python
    start = Task(
        name='start',
        upstreams=[
            start_app,
            start_mysql,
            start_redis,
        ]
    )
    runner.register(start)
    ```
    '''
    pass
