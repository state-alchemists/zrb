from typing import Any
from ..task.decorator import python_task
from ..task_input.str_input import StrInput
from ..runner import runner

# Common definitions


@python_task(
    name='eval',
    inputs=[
        StrInput(
            name='expression',
            shortcut='e',
            default='',
            description='Python expression',
        )
    ],
    description='Evaluate Python expression',
    retry=0,
    runner=runner
)
async def evaluate(*args: str, **kwargs: Any):
    expression: str = kwargs.get('expression', '')
    return eval(expression)
