from zrb.helper.typing import Any
from zrb.runner import runner
from zrb.task.decorator import python_task
from zrb.task_input.str_input import StrInput

###############################################################################
# Task Definitions
###############################################################################


@python_task(
    name="eval",
    inputs=[
        StrInput(
            name="expression",
            shortcut="e",
            default="",
            description="Python expression",
        )
    ],
    description="Evaluate Python expression",
    retry=0,
    runner=runner,
)
async def evaluate(*args: str, **kwargs: Any):
    expression: str = kwargs.get("expression", "")
    return eval(expression)
