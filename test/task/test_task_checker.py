from zrb.task.checker import Checker
from zrb.task.task import Task
from zrb.task_input.str_input import StrInput
from zrb.task_env.env import Env
import asyncio


class DelayedChecker(Checker):
    async def inspect(self, *args, **kwargs) -> bool:
        await asyncio.sleep(1)
        return True


def test_use_the_same_task_for_checker_and_upstream():
    delayed_checker = DelayedChecker()
    # use delayed_chacker as task_1 checker
    task_1 = Task(
        name='task-1',
        inputs=[StrInput(name='input-1')],
        envs=[Env(name='ENV1')],
        checkers=[delayed_checker]
    )
    # use delayed_chacker as task_2 checker
    task_2 = Task(
        name='task-2',
        inputs=[StrInput(name='input-2')],
        envs=[Env(name='ENV2')],
    )
    task_2.add_checker(delayed_checker)
    # use delayed_chacker as task_3 upstream
    task = Task(
        name='task',
        upstreams=[task_1, task_2, delayed_checker]
    )
    fn = task.to_function()
    fn()
