import hashlib

import aiofiles

from zrb.builtin.group import md5_group
from zrb.helper.typing import Any
from zrb.runner import runner
from zrb.task.decorator import python_task
from zrb.task_input.str_input import StrInput

###############################################################################
# Task Definitions
###############################################################################


@python_task(
    name="hash",
    group=md5_group,
    inputs=[StrInput(name="text", shortcut="t", description="Text", default="")],
    description="Hash md5",
    retry=0,
    runner=runner,
)
async def hash_text(*args: str, **kwargs: Any):
    text: str = kwargs.get("text", "")
    hashed_text = hashlib.md5(text.encode()).hexdigest()
    return hashed_text


@python_task(
    name="sum",
    group=md5_group,
    inputs=[StrInput(name="file", shortcut="f", description="File", default="")],
    description="Sum md5 file",
    retry=0,
    runner=runner,
)
async def sum_file(*args: str, **kwargs: Any):
    file_path: str = kwargs.get("file", "")
    async with aiofiles.open(file_path, mode="rb") as file:
        contents = await file.read()
    hashed_text = hashlib.md5(contents).hexdigest()
    return hashed_text
