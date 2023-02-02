from typing import Any, Callable
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

    def create_main_loop(
        self, env_prefix: str = ''
    ) -> Callable[..., bool]:
        return super().create_main_loop(env_prefix)

    async def run(self, **kwargs: Any) -> bool:
        await super().run(**kwargs)
        return True
