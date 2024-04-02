import hashlib

import aiofiles

from zrb.builtin.md5._group import md5_group
from zrb.helper.typing import Any
from zrb.runner import runner
from zrb.task.decorator import python_task
from zrb.task_input.str_input import StrInput


@python_task(
    name="sum",
    group=md5_group,
    inputs=[StrInput(name="file", shortcut="f", description="File", default="")],
    description="Sum md5 file",
    retry=0,
    runner=runner,
)
async def sum_file_md5(*args: str, **kwargs: Any):
    file_path: str = kwargs.get("file", "")
    async with aiofiles.open(file_path, mode="rb") as file:
        contents = await file.read()
    hashed_text = hashlib.md5(contents).hexdigest()
    return hashed_text
