import hashlib

from zrb.builtin.md5._group import md5_group
from zrb.helper.typing import Any
from zrb.runner import runner
from zrb.task.decorator import python_task
from zrb.task_input.str_input import StrInput


@python_task(
    name="hash",
    group=md5_group,
    inputs=[StrInput(name="text", shortcut="t", description="Text", default="")],
    description="Hash md5",
    retry=0,
    runner=runner,
)
async def hash_text_md5(*args: str, **kwargs: Any):
    text: str = kwargs.get("text", "")
    hashed_text = hashlib.md5(text.encode()).hexdigest()
    return hashed_text
