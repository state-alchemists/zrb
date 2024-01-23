from typing import Any

from zrb import Task

HELLO_WORLD = "👋🌍"


class ExampleTask(Task):
    """
    ExampleTask, write "Hello World" in emoji.
    """

    async def run(self, *args: Any, **kwargs: Any) -> Any:
        task: Task = kwargs.get("_task")
        task.print_out(HELLO_WORLD)
        return HELLO_WORLD
