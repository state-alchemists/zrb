from typing import Any
from ..task.task import Task
from ..task_input.str_input import StrInput
from ..runner import runner

# Common definitions


def _evaluate(*args: str, **kwargs: Any):
    expression: str = kwargs.get('expression', '')
    return eval(expression)


# Task definitions

eval_task = Task(
    name='eval',
    inputs=[
        StrInput(
            name='expression',
            shortcut='e',
            default='',
            description='Python expression',
        )
    ],
    run=_evaluate,
    description='Evaluate Python expression',
    retry=0
)
runner.register(eval_task)
